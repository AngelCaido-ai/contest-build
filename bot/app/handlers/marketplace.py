from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.app.services import api_client

router = Router()

MENU_MAIN = "menu:main"
MENU_LISTINGS = "menu:listings"
MENU_REQUESTS = "menu:requests"
MENU_DEALS = "menu:deals"
MENU_CREATE_LISTING = "menu:create_listing"
MENU_CREATE_REQUEST = "menu:create_request"
LISTING_PREFIX = "listing:"
LISTING_RESPOND_PREFIX = "listing_respond:"
REQUEST_PREFIX = "request:"
LISTING_CHANNEL_PREFIX = "listing_channel:"
LISTING_CHANNEL_MANUAL = "listing_channel_manual"
FLOW_BACK_PREFIX = "flow_back:"
FLOW_CANCEL_PREFIX = "flow_cancel:"


class ListingCreateState(StatesGroup):
    channel_id = State()
    price_usd = State()
    format = State()


class ListingRespondState(StatesGroup):
    listing_id = State()
    price_usd = State()
    format = State()
    brief = State()


class RequestCreateState(StatesGroup):
    budget = State()
    brief = State()


def _is_number(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def _is_skip(value: str) -> bool:
    return value.lower() in {"skip", "-"}


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if not value:
        return value
    if value[0] in {'"', "'", "“", "”"} and len(value) > 1 and value[-1] == value[0]:
        value = value[1:-1].strip()
    return value


def _is_int(value: str) -> bool:
    if not value:
        return False
    if value[0] == "-":
        return value[1:].isdigit()
    return value.isdigit()


def _extract_channel_ref(value: str) -> str:
    value = _strip_quotes(value)
    if not value:
        return value
    if _is_int(value):
        return value
    raw = value
    for prefix in ("https://", "http://"):
        if raw.startswith(prefix):
            raw = raw[len(prefix) :]
            break
    for domain in ("t.me/", "telegram.me/"):
        if raw.startswith(domain):
            raw = raw[len(domain) :]
            break
    raw = raw.lstrip("/")
    raw = raw.split("?", 1)[0]
    if raw.startswith("c/"):
        parts = raw.split("/")
        if len(parts) >= 2 and parts[1].isdigit():
            return f"-100{parts[1]}"
    if "/" in raw:
        raw = raw.split("/", 1)[0]
    if raw.startswith("@"):
        raw = raw[1:]
    return raw.strip()


def _find_channel(
    items: list[dict],
    *,
    channel_id: int | None = None,
    tg_chat_id: int | None = None,
    username: str | None = None,
) -> dict | None:
    username_norm = (username or "").lower()
    for item in items:
        if channel_id is not None and item.get("id") == channel_id:
            return item
        if tg_chat_id is not None and item.get("tg_chat_id") == tg_chat_id:
            return item
        if username_norm and (item.get("username") or "").lower() == username_norm:
            return item
    return None


async def _link_channel(message: Message, bot: Bot, chat) -> int | None:
    try:
        user_member = await bot.get_chat_member(chat.id, message.from_user.id)
        bot_member = await bot.get_chat_member(chat.id, (await bot.me()).id)
    except TelegramBadRequest:
        await message.answer("Cannot access member list. Make bot admin or use a public channel.")
        return None
    user_admin = user_member.status in {"administrator", "creator"}
    bot_admin = bot_member.status in {"administrator", "creator"}
    if not user_admin:
        await message.answer("You are not channel admin.")
        return None
    payload = {
        "owner_tg_user_id": message.from_user.id,
        "tg_chat_id": chat.id,
        "username": chat.username,
        "title": chat.title,
        "bot_admin_status": bot_admin,
        "rights_snapshot": {
            "user_status": user_member.status,
            "bot_status": bot_member.status,
        },
    }
    try:
        result = api_client.create_channel(payload)
    except Exception as exc:
        await message.answer(f"Failed to link channel: {exc}")
        return None
    channel_id = result.get("channel_id")
    if channel_id is None:
        await message.answer("Failed to link channel.")
        return None
    return int(channel_id)


async def _resolve_channel_id(message: Message, bot: Bot, value: str) -> int | None:
    ref = _extract_channel_ref(value)
    if not ref:
        await message.answer("Enter @username, t.me link, or channel id.")
        return None
    if _is_int(ref):
        number = int(ref)
        try:
            items = api_client.list_channels(message.from_user.id)
        except Exception:
            items = []
        if number > 0:
            if _find_channel(items, channel_id=number):
                return number
            await message.answer("Channel not found. Send @username or t.me link.")
            return None
        match = _find_channel(items, tg_chat_id=number)
        if match:
            return match.get("id")
        try:
            chat = await bot.get_chat(number)
        except Exception:
            await message.answer("Channel not found. Make sure the bot is an admin.")
            return None
        return await _link_channel(message, bot, chat)
    try:
        items = api_client.list_channels(message.from_user.id)
    except Exception:
        items = []
    match = _find_channel(items, username=ref)
    if match:
        return match.get("id")
    try:
        chat = await bot.get_chat(f"@{ref}")
    except Exception:
        await message.answer("Channel not found. Send @username or a valid t.me link.")
        return None
    return await _link_channel(message, bot, chat)


class CommandTextFilter(BaseFilter):
    def __init__(self, command: str) -> None:
        self.command = command

    async def __call__(self, message: Message) -> bool:
        command = _extract_command(message.text)
        return command == self.command


def _extract_command(text: str | None) -> str | None:
    value = (text or "").strip()
    if not value:
        return None
    if value[0] in {'"', "'", "“", "”"} and len(value) > 1 and value[-1] == value[0]:
        value = value[1:-1].strip()
    first = value.split()[0].lstrip("/")
    first = first.strip('"\'' "“”")
    if "@" in first:
        first = first.split("@", 1)[0]
    return first


def _main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Listings", callback_data=MENU_LISTINGS)
    builder.button(text="Requests", callback_data=MENU_REQUESTS)
    builder.button(text="Deals", callback_data=MENU_DEALS)
    builder.button(text="Create listing", callback_data=MENU_CREATE_LISTING)
    builder.button(text="Create request", callback_data=MENU_CREATE_REQUEST)
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def _items_keyboard(items: list[dict], prefix: str):
    builder = InlineKeyboardBuilder()
    for item in items[:10]:
        item_id = item.get("id")
        if item_id is None:
            continue
        builder.button(text=f"#{item_id}", callback_data=f"{prefix}{item_id}")
    builder.button(text="Back to menu", callback_data=MENU_MAIN)
    builder.adjust(2)
    return builder.as_markup()


def _flow_nav_keyboard(back_data: str | None, cancel_data: str):
    builder = InlineKeyboardBuilder()
    if back_data:
        builder.button(text="Назад", callback_data=back_data)
    builder.button(text="Отмена", callback_data=cancel_data)
    builder.adjust(2)
    return builder.as_markup()


async def _prompt_listing_channel_select(message: Message, tg_user_id: int) -> None:
    try:
        items = api_client.list_channels(tg_user_id)
    except Exception as exc:
        await message.answer(f"Failed to load channels: {exc}")
        await _prompt_listing_channel_manual(message)
        return
    if not items:
        await message.answer("No channels found.")
        await _prompt_listing_channel_manual(message)
        return
    builder = InlineKeyboardBuilder()
    for item in items[:10]:
        item_id = item.get("id")
        if item_id is None:
            continue
        label = item.get("title") or item.get("username") or item.get("tg_chat_id") or item_id
        builder.button(text=f"#{item_id} {label}", callback_data=f"{LISTING_CHANNEL_PREFIX}{item_id}")
    builder.button(text="Ввести вручную", callback_data=LISTING_CHANNEL_MANUAL)
    builder.button(text="Назад", callback_data=f"{FLOW_BACK_PREFIX}listing:menu")
    builder.button(text="Отмена", callback_data=f"{FLOW_CANCEL_PREFIX}listing")
    builder.adjust(1)
    await message.answer("Выберите канал для листинга:", reply_markup=builder.as_markup())


async def _prompt_listing_channel_manual(message: Message) -> None:
    await message.answer(
        "Введите @username, ссылку t.me/... или числовой id канала (-100...).",
        reply_markup=_flow_nav_keyboard(f"{FLOW_BACK_PREFIX}listing:menu", f"{FLOW_CANCEL_PREFIX}listing"),
    )


async def _prompt_listing_price(message: Message) -> None:
    await message.answer(
        "Enter price in USD or 'skip'.",
        reply_markup=_flow_nav_keyboard(f"{FLOW_BACK_PREFIX}listing:channel_id", f"{FLOW_CANCEL_PREFIX}listing"),
    )


async def _prompt_listing_format(message: Message) -> None:
    await message.answer(
        "Enter format or 'skip'.",
        reply_markup=_flow_nav_keyboard(f"{FLOW_BACK_PREFIX}listing:price_usd", f"{FLOW_CANCEL_PREFIX}listing"),
    )


async def _prompt_listing_respond_price(message: Message) -> None:
    await message.answer(
        "Enter price in USD or 'skip' to use listing price.",
        reply_markup=_flow_nav_keyboard(None, f"{FLOW_CANCEL_PREFIX}listing_respond"),
    )


async def _prompt_listing_respond_format(message: Message) -> None:
    await message.answer(
        "Enter format or 'skip' to use listing format.",
        reply_markup=_flow_nav_keyboard(None, f"{FLOW_CANCEL_PREFIX}listing_respond"),
    )


async def _prompt_listing_respond_brief(message: Message) -> None:
    await message.answer(
        "Enter brief or 'skip'.",
        reply_markup=_flow_nav_keyboard(None, f"{FLOW_CANCEL_PREFIX}listing_respond"),
    )


async def _prompt_request_budget(message: Message) -> None:
    await message.answer(
        "Enter budget in USD or 'skip'.",
        reply_markup=_flow_nav_keyboard(f"{FLOW_BACK_PREFIX}request:menu", f"{FLOW_CANCEL_PREFIX}request"),
    )


async def _prompt_request_brief(message: Message) -> None:
    await message.answer(
        "Enter brief or 'skip'.",
        reply_markup=_flow_nav_keyboard(f"{FLOW_BACK_PREFIX}request:budget", f"{FLOW_CANCEL_PREFIX}request"),
    )


async def _send_listings(message: Message) -> None:
    try:
        items = api_client.list_listings()
    except Exception as exc:
        await message.answer(f"Failed to load listings: {exc}")
        return
    if not items:
        await message.answer("No listings found", reply_markup=_main_menu_keyboard())
        return
    lines = []
    for item in items[:10]:
        price = item.get("price_usd")
        price_label = "-" if price is None else price
        lines.append(
            f"#{item.get('id')} channel={item.get('channel_id')} price={price_label} format={item.get('format')}"
        )
    if len(items) > 10:
        lines.append(f"... {len(items) - 10} more")
    await message.answer("\n".join(lines), reply_markup=_items_keyboard(items, LISTING_PREFIX))


async def _send_requests(message: Message) -> None:
    try:
        items = api_client.list_requests()
    except Exception as exc:
        await message.answer(f"Failed to load requests: {exc}")
        return
    if not items:
        await message.answer("No requests found", reply_markup=_main_menu_keyboard())
        return
    lines = []
    for item in items[:10]:
        budget = item.get("budget")
        budget_label = "-" if budget is None else budget
        brief = item.get("brief") or ""
        lines.append(f"#{item.get('id')} budget={budget_label} brief={brief}")
    if len(items) > 10:
        lines.append(f"... {len(items) - 10} more")
    await message.answer("\n".join(lines), reply_markup=_items_keyboard(items, REQUEST_PREFIX))


async def _send_deals(message: Message, tg_user_id: int | None = None) -> None:
    try:
        user_id = tg_user_id if tg_user_id is not None else message.from_user.id
        items = api_client.list_deals(user_id)
    except Exception as exc:
        await message.answer(f"Failed to load deals: {exc}")
        return
    if not items:
        await message.answer("No deals found", reply_markup=_main_menu_keyboard())
        return
    lines = []
    for item in items[:10]:
        lines.append(f"#{item.get('id')} status={item.get('status')}")
    if len(items) > 10:
        lines.append(f"... {len(items) - 10} more")
    await message.answer("\n".join(lines), reply_markup=_items_keyboard(items, "deal:"))


@router.message(Command("menu"))
@router.message(CommandTextFilter("menu"))
async def show_menu(message: Message) -> None:
    await message.answer("Choose an action:", reply_markup=_main_menu_keyboard())


@router.message(Command("cancel"))
async def cancel_flow(message: Message, state: FSMContext) -> None:
    if await state.get_state():
        await state.clear()
    await message.answer("Canceled.", reply_markup=_main_menu_keyboard())
@router.message(Command("listings"))
async def list_listings(message: Message) -> None:
    await _send_listings(message)


@router.message(Command("requests"))
async def list_requests(message: Message) -> None:
    await _send_requests(message)


@router.message(Command("channels"))
async def list_channels(message: Message) -> None:
    try:
        items = api_client.list_channels(message.from_user.id)
    except Exception as exc:
        await message.answer(f"Failed to load channels: {exc}")
        return
    if not items:
        await message.answer("No channels found", reply_markup=_main_menu_keyboard())
        return
    lines = []
    for item in items[:10]:
        username = item.get("username") or "-"
        title = item.get("title") or "-"
        lines.append(
            f"#{item.get('id')} tg_chat_id={item.get('tg_chat_id')} username={username} title={title}"
        )
    if len(items) > 10:
        lines.append(f"... {len(items) - 10} more")
    await message.answer("\n".join(lines), reply_markup=_main_menu_keyboard())


@router.message(Command("respond_request"))
@router.message(CommandTextFilter("respond_request"))
async def respond_request(message: Message) -> None:
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer(
            "Usage: /respond_request REQUEST_ID CHANNEL_ID [PRICE] [FORMAT] [PUBLISH_AT_ISO] [VERIFICATION_MINUTES]"
        )
        return
    request_id = int(parts[1])
    channel_id = int(parts[2])
    price = float(parts[3]) if len(parts) > 3 else None
    format_value = parts[4] if len(parts) > 4 else None
    publish_at = parts[5] if len(parts) > 5 else None
    verification_window = int(parts[6]) if len(parts) > 6 else None
    payload = {
        "owner_tg_user_id": message.from_user.id,
        "request_id": request_id,
        "channel_id": channel_id,
        "price": price,
        "format": format_value,
        "publish_at": publish_at,
        "verification_window": verification_window,
    }
    try:
        deal = api_client.create_deal(payload)
        await message.answer(f"Deal created: #{deal.get('id')}", reply_markup=_main_menu_keyboard())
    except Exception as exc:
        await message.answer(f"Failed to create deal: {exc}")


@router.message(Command("deals"))
async def list_deals(message: Message) -> None:
    await _send_deals(message)


@router.message(Command("create_request"))
async def create_request(message: Message, state: FSMContext) -> None:
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2:
        await state.set_state(RequestCreateState.budget)
        await _prompt_request_budget(message)
        return
    budget = None
    brief = None
    if len(parts) == 2:
        if _is_number(parts[1]):
            budget = float(parts[1])
        else:
            brief = parts[1]
    else:
        if _is_number(parts[1]):
            budget = float(parts[1])
            brief = parts[2]
        else:
            brief = (message.text or "").split(maxsplit=1)[1]
    payload = {
        "advertiser_tg_user_id": message.from_user.id,
        "budget": budget,
        "brief": brief,
    }
    try:
        api_client.create_request(payload)
        await message.answer("Request created", reply_markup=_main_menu_keyboard())
    except Exception as exc:
        await message.answer(f"Failed to create request: {exc}")


@router.message(Command("create_listing"))
async def create_listing(message: Message, state: FSMContext, bot: Bot) -> None:
    parts = (message.text or "").split()
    if len(parts) < 2:
        await state.set_state(ListingCreateState.channel_id)
        await _prompt_listing_channel_select(message, message.from_user.id)
        return
    channel_id = await _resolve_channel_id(message, bot, parts[1])
    if channel_id is None:
        return
    price_usd = float(parts[2]) if len(parts) > 2 else None
    format_value = parts[3] if len(parts) > 3 else "post"
    payload = {
        "owner_tg_user_id": message.from_user.id,
        "channel_id": channel_id,
        "price_usd": price_usd,
        "format": format_value,
    }
    try:
        api_client.create_listing(payload)
        await message.answer("Listing created", reply_markup=_main_menu_keyboard())
    except Exception as exc:
        await message.answer(f"Failed to create listing: {exc}")


@router.callback_query(F.data == MENU_MAIN)
async def menu_main(callback: CallbackQuery) -> None:
    if callback.message:
        await callback.message.answer("Choose an action:", reply_markup=_main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == MENU_LISTINGS)
async def menu_listings(callback: CallbackQuery) -> None:
    if callback.message:
        await _send_listings(callback.message)
    await callback.answer()


@router.callback_query(F.data == MENU_REQUESTS)
async def menu_requests(callback: CallbackQuery) -> None:
    if callback.message:
        await _send_requests(callback.message)
    await callback.answer()


@router.callback_query(F.data == MENU_DEALS)
async def menu_deals(callback: CallbackQuery) -> None:
    if callback.message:
        await _send_deals(callback.message, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == MENU_CREATE_LISTING)
async def menu_create_listing(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ListingCreateState.channel_id)
    if callback.message:
        await _prompt_listing_channel_select(callback.message, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == MENU_CREATE_REQUEST)
async def menu_create_request(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(RequestCreateState.budget)
    if callback.message:
        await _prompt_request_budget(callback.message)
    await callback.answer()


@router.callback_query(F.data.startswith(FLOW_BACK_PREFIX))
async def flow_back(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    _, flow, step = callback.data.split(":", 2)
    if step == "menu":
        if await state.get_state():
            await state.clear()
        await callback.message.answer("Choose an action:", reply_markup=_main_menu_keyboard())
        await callback.answer()
        return
    if flow == "listing":
        if step == "channel_id":
            await state.set_state(ListingCreateState.channel_id)
            await _prompt_listing_channel_select(callback.message, callback.from_user.id)
        if step == "price_usd":
            await state.set_state(ListingCreateState.price_usd)
            await _prompt_listing_price(callback.message)
    if flow == "request":
        if step == "budget":
            await state.set_state(RequestCreateState.budget)
            await _prompt_request_budget(callback.message)
    await callback.answer()


@router.callback_query(F.data.startswith(FLOW_CANCEL_PREFIX))
async def flow_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    if await state.get_state():
        await state.clear()
    await callback.message.answer("Canceled.", reply_markup=_main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith(LISTING_CHANNEL_PREFIX))
async def listing_channel_selected(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    channel_id = int(callback.data.split(":", 1)[1])
    await state.update_data(channel_id=channel_id)
    await state.set_state(ListingCreateState.price_usd)
    await _prompt_listing_price(callback.message)
    await callback.answer()


@router.callback_query(F.data == LISTING_CHANNEL_MANUAL)
async def listing_channel_manual(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        await callback.answer()
        return
    await state.set_state(ListingCreateState.channel_id)
    await _prompt_listing_channel_manual(callback.message)
    await callback.answer()


@router.callback_query(F.data.startswith(LISTING_PREFIX))
async def listing_details(callback: CallbackQuery) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    listing_id = int(callback.data.split(":", 1)[1])
    try:
        listing = api_client.get_listing(listing_id)
    except Exception as exc:
        await callback.message.answer(f"Failed to load listing: {exc}")
        await callback.answer()
        return
    is_own = False
    try:
        channels = api_client.list_channels(callback.from_user.id)
        is_own = any(item.get("id") == listing.get("channel_id") for item in channels)
    except Exception:
        is_own = False
    text = "\n".join(
        [
            f"Listing #{listing.get('id')}",
            f"channel_id: {listing.get('channel_id')}",
            f"price_usd: {listing.get('price_usd')}",
            f"price_ton: {listing.get('price_ton')}",
            f"format: {listing.get('format')}",
            f"active: {listing.get('active')}",
        ]
    )
    if is_own:
        text = f"{text}\nYou cannot respond to your own listing."
    builder = InlineKeyboardBuilder()
    if not is_own:
        builder.button(text="Respond", callback_data=f"{LISTING_RESPOND_PREFIX}{listing_id}")
    builder.button(text="Back to listings", callback_data=MENU_LISTINGS)
    builder.button(text="Back to menu", callback_data=MENU_MAIN)
    if is_own:
        builder.adjust(1, 1)
    else:
        builder.adjust(1, 1, 1)
    await callback.message.answer(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith(LISTING_RESPOND_PREFIX))
async def listing_respond_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    listing_id = int(callback.data.split(":", 1)[1])
    try:
        listing = api_client.get_listing(listing_id)
    except Exception as exc:
        await callback.message.answer(f"Failed to load listing: {exc}")
        await callback.answer()
        return
    if not listing.get("active", True):
        await callback.message.answer("Listing is inactive.", reply_markup=_main_menu_keyboard())
        await callback.answer()
        return
    try:
        channels = api_client.list_channels(callback.from_user.id)
    except Exception as exc:
        await callback.message.answer(f"Failed to load channels: {exc}")
        await callback.answer()
        return
    if any(item.get("id") == listing.get("channel_id") for item in channels):
        await callback.message.answer("You cannot respond to your own listing.", reply_markup=_main_menu_keyboard())
        await callback.answer()
        return
    await state.set_state(ListingRespondState.price_usd)
    await state.update_data(listing_id=listing_id)
    await _prompt_listing_respond_price(callback.message)
    await callback.answer()


@router.callback_query(F.data.startswith(REQUEST_PREFIX))
async def request_details(callback: CallbackQuery) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    request_id = int(callback.data.split(":", 1)[1])
    try:
        request_item = api_client.get_request(request_id)
    except Exception as exc:
        await callback.message.answer(f"Failed to load request: {exc}")
        await callback.answer()
        return
    text = "\n".join(
        [
            f"Request #{request_item.get('id')}",
            f"budget: {request_item.get('budget')}",
            f"niche: {request_item.get('niche')}",
            f"languages: {request_item.get('languages')}",
            f"min_subs: {request_item.get('min_subs')}",
            f"min_views: {request_item.get('min_views')}",
            f"dates: {request_item.get('dates')}",
            f"brief: {request_item.get('brief')}",
        ]
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="Back to requests", callback_data=MENU_REQUESTS)
    builder.button(text="Back to menu", callback_data=MENU_MAIN)
    builder.adjust(1, 1)
    await callback.message.answer(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.message(ListingCreateState.channel_id)
async def listing_channel_id(message: Message, state: FSMContext, bot: Bot) -> None:
    value = (message.text or "").strip()
    channel_id = await _resolve_channel_id(message, bot, value)
    if channel_id is None:
        return
    await state.update_data(channel_id=channel_id)
    await state.set_state(ListingCreateState.price_usd)
    await _prompt_listing_price(message)


@router.message(ListingCreateState.price_usd)
async def listing_price(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if _is_skip(value):
        await state.update_data(price_usd=None)
    elif _is_number(value):
        await state.update_data(price_usd=float(value))
    else:
        await message.answer("Price must be a number or 'skip'.")
        return
    await state.set_state(ListingCreateState.format)
    await _prompt_listing_format(message)


@router.message(ListingCreateState.format)
async def listing_format(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    format_value = None if _is_skip(value) else value
    data = await state.get_data()
    payload = {
        "owner_tg_user_id": message.from_user.id,
        "channel_id": data["channel_id"],
        "price_usd": data.get("price_usd"),
        "format": format_value or "post",
    }
    try:
        api_client.create_listing(payload)
        await message.answer("Listing created", reply_markup=_main_menu_keyboard())
    except Exception as exc:
        await message.answer(f"Failed to create listing: {exc}")
    await state.clear()


@router.message(ListingRespondState.price_usd)
async def listing_respond_price(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if _is_skip(value):
        await state.update_data(price_usd=None)
    elif _is_number(value):
        await state.update_data(price_usd=float(value))
    else:
        await message.answer("Price must be a number or 'skip'.")
        return
    await state.set_state(ListingRespondState.format)
    await _prompt_listing_respond_format(message)


@router.message(ListingRespondState.format)
async def listing_respond_format(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    format_value = None if _is_skip(value) else value
    await state.update_data(format=format_value)
    await state.set_state(ListingRespondState.brief)
    await _prompt_listing_respond_brief(message)


@router.message(ListingRespondState.brief)
async def listing_respond_brief(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    brief_value = None if _is_skip(value) else value
    data = await state.get_data()
    listing_id = data.get("listing_id")
    if listing_id is None:
        await message.answer("Listing not found.", reply_markup=_main_menu_keyboard())
        await state.clear()
        return
    try:
        listing = api_client.get_listing(int(listing_id))
    except Exception as exc:
        await message.answer(f"Failed to load listing: {exc}")
        await state.clear()
        return
    price = data.get("price_usd")
    if price is None:
        price = listing.get("price_usd")
    format_value = data.get("format") or listing.get("format") or "post"
    payload = {
        "owner_tg_user_id": message.from_user.id,
        "listing_id": int(listing_id),
        "price": price,
        "format": format_value,
        "brief": brief_value,
    }
    try:
        deal = api_client.create_deal(payload)
        await message.answer(f"Deal created: #{deal.get('id')}")
        try:
            from bot.app.handlers.deals import _send_deal_details
        except Exception:
            await message.answer("Use /deal to open the deal.", reply_markup=_main_menu_keyboard())
            await state.clear()
            return
        await _send_deal_details(message, int(deal.get("id")))
    except Exception as exc:
        await message.answer(f"Failed to create deal: {exc}")
    await state.clear()


@router.message(RequestCreateState.budget)
async def request_budget(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if _is_skip(value):
        await state.update_data(budget=None)
    elif _is_number(value):
        await state.update_data(budget=float(value))
    else:
        await message.answer("Budget must be a number or 'skip'.")
        return
    await state.set_state(RequestCreateState.brief)
    await _prompt_request_brief(message)


@router.message(RequestCreateState.brief)
async def request_brief(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    brief = None if _is_skip(value) else value
    data = await state.get_data()
    payload = {
        "advertiser_tg_user_id": message.from_user.id,
        "budget": data.get("budget"),
        "brief": brief,
    }
    try:
        api_client.create_request(payload)
        await message.answer("Request created", reply_markup=_main_menu_keyboard())
    except Exception as exc:
        await message.answer(f"Failed to create request: {exc}")
    await state.clear()
