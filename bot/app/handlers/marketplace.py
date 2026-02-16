import logging
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.app.services import api_client

logger = logging.getLogger(__name__)
router = Router()

MENU_MAIN = "menu:main"
MENU_LISTINGS = "menu:listings"
MENU_REQUESTS = "menu:requests"
MENU_DEALS = "menu:deals"
MENU_CREATE_LISTING = "menu:create_listing"
MENU_CREATE_REQUEST = "menu:create_request"
MENU_WALLET = "menu:wallet"
LISTING_PREFIX = "listing:"
LISTING_RESPOND_PREFIX = "listing_respond:"
REQUEST_PREFIX = "request:"
LISTING_CHANNEL_PREFIX = "listing_channel:"
LISTING_CHANNEL_MANUAL = "listing_channel_manual"
FLOW_BACK_PREFIX = "flow_back:"
FLOW_CANCEL_PREFIX = "flow_cancel:"
MANAGER_CHANNEL_PREFIX = "manager_channel:"
MANAGER_CHANNEL_MANUAL = "manager_channel_manual"
MANAGER_REMOVE_CONFIRM_PREFIX = "manager_remove_confirm:"
DEALS_PAGE_PREFIX = "deals_page:"
DEALS_STATUS_PREFIX = "deals_status:"
DEALS_ROLE_PREFIX = "deals_role:"
DEALS_CHANNEL_PREFIX = "deals_channel:"
DEALS_CLEAR_PREFIX = "deals_clear"
DEALS_ACTIVE_CLEAR_PREFIX = "deals_active_clear"
LISTINGS_PAGE_PREFIX = "listings_page:"
REQUESTS_PAGE_PREFIX = "requests_page:"

DEAL_LIST_FILTERS_KEY = "deal_list_filters"
ACTIVE_DEAL_KEY = "active_deal_id"
ACTIVE_DEAL_PIN_KEY = "active_deal_pinned_message_id"
DEAL_DRAFTS_KEY = "deal_drafts"
DEALS_PAGE_SIZE = 8
DEALS_ORDER_BY = "updated_at_desc"
LISTINGS_PAGE_SIZE = 8
REQUESTS_PAGE_SIZE = 8
LISTING_LIST_PAGE_KEY = "listing_list_page"
REQUEST_LIST_PAGE_KEY = "request_list_page"


class ListingCreateState(StatesGroup):
    channel_id = State()
    price_usd = State()
    format = State()


class ListingRespondState(StatesGroup):
    listing_id = State()
    price_usd = State()
    format = State()
    brief = State()
    publish_at = State()
    creative = State()


class RequestCreateState(StatesGroup):
    budget = State()
    brief = State()


class WalletState(StatesGroup):
    address = State()


class ManagerAddState(StatesGroup):
    channel_id = State()
    username = State()


class ManagerListState(StatesGroup):
    channel_id = State()


class ManagerRemoveState(StatesGroup):
    channel_id = State()
    username = State()
    confirm = State()


class DealListFilterState(StatesGroup):
    channel_id = State()


DEAL_STATUS_GROUPS = {
    "all": {"label": "All", "statuses": None},
    "negotiating": {"label": "Negotiating", "statuses": ["NEGOTIATING", "TERMS_LOCKED"]},
    "payment": {"label": "Payment", "statuses": ["AWAITING_PAYMENT", "FUNDED"]},
    "creative": {"label": "Creative", "statuses": ["CREATIVE_DRAFT", "CREATIVE_REVIEW"]},
    "publish": {"label": "Publishing", "statuses": ["APPROVED", "SCHEDULED", "POSTED"]},
    "verify": {"label": "Verification", "statuses": ["VERIFYING"]},
    "done": {"label": "Completed", "statuses": ["RELEASED", "REFUNDED", "CANCELED"]},
}
DEAL_STATUS_GROUP_ORDER = list(DEAL_STATUS_GROUPS.keys())
DEAL_ROLE_OPTIONS = ["all", "owner", "advertiser"]
DEAL_ROLE_LABELS = {
    "all": "All",
    "owner": "My channels",
    "advertiser": "I'm advertiser",
}


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


def _normalize_username(value: str) -> str | None:
    value = _strip_quotes(value)
    if not value:
        return None
    if value.startswith("@"):
        value = value[1:]
    value = value.strip().lower()
    return value or None


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
        result = await api_client.create_channel(payload)
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
            items = await api_client.list_channels(message.from_user.id)
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
        items = await api_client.list_channels(message.from_user.id)
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


async def _clear_state_keep(state: FSMContext) -> dict:
    data = await state.get_data()
    keep_keys = {ACTIVE_DEAL_KEY, ACTIVE_DEAL_PIN_KEY, DEAL_DRAFTS_KEY, DEAL_LIST_FILTERS_KEY}
    keep = {key: data[key] for key in keep_keys if key in data}
    await state.clear()
    if keep:
        await state.update_data(**keep)
    return keep


def _default_deal_filters() -> dict:
    return {"status_group": "all", "role": "all", "channel_id": None, "page": 0}


async def _get_deal_filters(state: FSMContext) -> dict:
    data = await state.get_data()
    filters = data.get(DEAL_LIST_FILTERS_KEY) or {}
    result = _default_deal_filters()
    result.update(filters)
    return result


async def _set_deal_filters(state: FSMContext, **updates) -> dict:
    filters = await _get_deal_filters(state)
    filters.update(updates)
    await state.update_data(**{DEAL_LIST_FILTERS_KEY: filters})
    return filters


def _cycle_value(current: str, options: list[str]) -> str:
    if current not in options:
        return options[0]
    index = options.index(current)
    return options[(index + 1) % len(options)]


def _deal_status_label(group: str) -> str:
    return (DEAL_STATUS_GROUPS.get(group) or DEAL_STATUS_GROUPS["all"]).get("label") or "All"


def _deal_role_label(role: str) -> str:
    return DEAL_ROLE_LABELS.get(role, DEAL_ROLE_LABELS["all"])


def _deal_channel_label(channel_id: int | None) -> str:
    return "All" if channel_id is None else f"#{channel_id}"


def _deal_statuses_for_group(group: str) -> list[str] | None:
    entry = DEAL_STATUS_GROUPS.get(group)
    if not entry:
        return None
    return entry.get("statuses")


def _main_menu_keyboard(has_wallet: bool = False):
    builder = InlineKeyboardBuilder()
    builder.button(text="Listings", callback_data=MENU_LISTINGS)
    builder.button(text="Requests", callback_data=MENU_REQUESTS)
    builder.button(text="Deals", callback_data=MENU_DEALS)
    builder.button(text="Create listing", callback_data=MENU_CREATE_LISTING)
    builder.button(text="Create request", callback_data=MENU_CREATE_REQUEST)
    if not has_wallet:
        builder.button(text="Set TON wallet", callback_data=MENU_WALLET)
        builder.adjust(2, 2, 2)
    else:
        builder.adjust(2, 2, 1)
    return builder.as_markup()


async def _main_menu_for_user(tg_user_id: int):
    """Build main menu keyboard, hiding 'Set TON wallet' if wallet already linked."""
    has_wallet = False
    try:
        data = await api_client.auth_bot(tg_user_id)
        user = data.get("user") or {}
        if user.get("linked_wallet"):
            has_wallet = True
    except Exception:
        logger.exception("_main_menu_for_user: wallet check failed tg_user_id=%s", tg_user_id)
    return _main_menu_keyboard(has_wallet=has_wallet)


def _items_keyboard(
    items: list[dict],
    prefix: str,
    *,
    page: int = 0,
    has_more: bool = False,
    page_prefix: str = "",
):
    builder = InlineKeyboardBuilder()
    for item in items:
        item_id = item.get("id")
        if item_id is None:
            continue
        builder.button(text=f"#{item_id}", callback_data=f"{prefix}{item_id}")
    builder.adjust(2)
    if page_prefix:
        nav_buttons: list[InlineKeyboardButton] = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="Prev", callback_data=f"{page_prefix}{page - 1}"))
        if has_more:
            nav_buttons.append(InlineKeyboardButton(text="Next", callback_data=f"{page_prefix}{page + 1}"))
        if nav_buttons:
            builder.row(*nav_buttons)
    builder.row(InlineKeyboardButton(text="Back to menu", callback_data=MENU_MAIN))
    return builder.as_markup()


def _flow_nav_keyboard(back_data: str | None, cancel_data: str):
    builder = InlineKeyboardBuilder()
    if back_data:
        builder.button(text="Back", callback_data=back_data)
    builder.button(text="Cancel", callback_data=cancel_data)
    builder.adjust(2)
    return builder.as_markup()


async def _prompt_wallet(message: Message) -> None:
    await message.answer(
        "Send TON wallet address for payouts.",
        reply_markup=_flow_nav_keyboard(f"{FLOW_BACK_PREFIX}wallet:menu", f"{FLOW_CANCEL_PREFIX}wallet"),
    )


async def _check_wallet(message: Message, tg_user_id: int) -> bool:
    try:
        data = await api_client.auth_bot(tg_user_id)
        user = data.get("user") or {}
        if user.get("linked_wallet"):
            return True
    except Exception:
        logger.exception("_check_wallet: failed for tg_user_id=%s", tg_user_id)
        return True
    builder = InlineKeyboardBuilder()
    builder.button(text="Link wallet", callback_data=MENU_WALLET)
    builder.adjust(1)
    await message.answer(
        "To create a listing, you need to link your TON wallet first.",
        reply_markup=builder.as_markup(),
    )
    return False


async def _prompt_listing_channel_select(message: Message, tg_user_id: int) -> None:
    try:
        items = await api_client.list_channels(tg_user_id)
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
    builder.button(text="Enter manually", callback_data=LISTING_CHANNEL_MANUAL)
    builder.button(text="Back", callback_data=f"{FLOW_BACK_PREFIX}listing:menu")
    builder.button(text="Cancel", callback_data=f"{FLOW_CANCEL_PREFIX}listing")
    builder.adjust(1)
    await message.answer("Select a channel for the listing:", reply_markup=builder.as_markup())


async def _prompt_listing_channel_manual(message: Message) -> None:
    await message.answer(
        "Enter @username, t.me/... link, or numeric channel id (-100...).",
        reply_markup=_flow_nav_keyboard(f"{FLOW_BACK_PREFIX}listing:menu", f"{FLOW_CANCEL_PREFIX}listing"),
    )


async def _prompt_manager_channel_select(message: Message, tg_user_id: int, flow: str) -> None:
    try:
        items = await api_client.list_channels(tg_user_id)
    except Exception as exc:
        await message.answer(f"Failed to load channels: {exc}")
        return
    if not items:
        await message.answer("No channels found.")
        return
    builder = InlineKeyboardBuilder()
    for item in items[:10]:
        item_id = item.get("id")
        if item_id is None:
            continue
        label = item.get("title") or item.get("username") or item.get("tg_chat_id") or item_id
        builder.button(text=f"#{item_id} {label}", callback_data=f"{MANAGER_CHANNEL_PREFIX}{flow}:{item_id}")
    builder.button(text="Enter manually", callback_data=f"{MANAGER_CHANNEL_MANUAL}:{flow}")
    builder.button(text="Cancel", callback_data=f"{FLOW_CANCEL_PREFIX}manager")
    builder.adjust(1)
    await message.answer("Select a channel for the manager:", reply_markup=builder.as_markup())


async def _prompt_manager_channel_manual(message: Message) -> None:
    await message.answer(
        "Enter @username, t.me/... link, or numeric channel id (-100...).",
        reply_markup=_flow_nav_keyboard(None, f"{FLOW_CANCEL_PREFIX}manager"),
    )


async def _prompt_manager_username(message: Message) -> None:
    await message.answer(
        "Enter manager @username.",
        reply_markup=_flow_nav_keyboard(None, f"{FLOW_CANCEL_PREFIX}manager"),
    )


async def _load_managers(message: Message, channel_id: int) -> list[dict] | None:
    try:
        items = await api_client.list_channel_managers(message.from_user.id, channel_id)
    except Exception as exc:
        await message.answer(f"Failed to load managers: {exc}")
        return None
    return items


async def _send_managers(message: Message, channel_id: int) -> None:
    items = await _load_managers(message, channel_id)
    if items is None:
        return
    if not items:
        await message.answer("No managers found.", reply_markup=_main_menu_keyboard())
        return
    lines = []
    for item in items[:10]:
        username = item.get("tg_username") or "-"
        lines.append(f"#{item.get('id')} tg_user_id={item.get('tg_user_id')} @{username}")
    if len(items) > 10:
        lines.append(f"... {len(items) - 10} more")
    await message.answer("\n".join(lines), reply_markup=_main_menu_keyboard())


async def _add_manager_by_username(message: Message, channel_id: int, username_raw: str) -> bool:
    username = _normalize_username(username_raw)
    if not username:
        await message.answer("Enter a valid @username.")
        return False
    try:
        await api_client.add_channel_manager(message.from_user.id, channel_id, username)
    except Exception as exc:
        await message.answer(f"Failed to add manager: {exc}")
        return False
    await message.answer("Manager added.", reply_markup=_main_menu_keyboard())
    return True


async def _prepare_remove_manager(
    message: Message,
    state: FSMContext,
    channel_id: int,
    username_raw: str,
) -> None:
    username = _normalize_username(username_raw)
    if not username:
        await message.answer("Enter a valid @username.")
        return
    items = await _load_managers(message, channel_id)
    if items is None:
        return
    manager = None
    for item in items:
        item_username = (item.get("tg_username") or "").lower()
        if item_username == username:
            manager = item
            break
    if not manager:
        await message.answer("Manager not found.")
        return
    manager_id = manager.get("id")
    if manager_id is None:
        await message.answer("Manager not found.")
        return
    await state.update_data(channel_id=channel_id, manager_id=manager_id, manager_username=username)
    await state.set_state(ManagerRemoveState.confirm)
    builder = InlineKeyboardBuilder()
    builder.button(text="Remove", callback_data=f"{MANAGER_REMOVE_CONFIRM_PREFIX}{channel_id}:{manager_id}")
    builder.button(text="Cancel", callback_data=f"{FLOW_CANCEL_PREFIX}manager")
    builder.adjust(2)
    await message.answer(f"Remove manager @{username}?", reply_markup=builder.as_markup())


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
        "Enter brief or 'skip'.\n"
        "Example:\n"
        "Product: ...\n"
        "Goal/CTA: ...\n"
        "Links: ...\n"
        "Restrictions: ...",
        reply_markup=_flow_nav_keyboard(None, f"{FLOW_CANCEL_PREFIX}listing_respond"),
    )


async def _prompt_listing_respond_publish_at(message: Message, state: FSMContext | None = None) -> None:
    from bot.app.keyboards.calendar import (
        CAL_CONTEXT_KEY,
        build_calendar_keyboard,
    )

    now = datetime.now()
    kb = build_calendar_keyboard(now.year, now.month, skip_allowed=True)
    if state:
        await state.update_data(**{CAL_CONTEXT_KEY: "listing_respond", "cal_skip_allowed": True})
    await message.answer("Select publish date:", reply_markup=kb.as_markup())


async def _prompt_listing_respond_creative(message: Message) -> None:
    await message.answer(
        "Send example creative text or attach media, or 'skip'.",
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


async def _send_listings(message: Message, state: FSMContext, *, edit: bool = False) -> None:
    data = await state.get_data()
    page = max(int(data.get(LISTING_LIST_PAGE_KEY) or 0), 0)
    limit = LISTINGS_PAGE_SIZE + 1
    offset = page * LISTINGS_PAGE_SIZE
    try:
        items = await api_client.list_listings(limit=limit, offset=offset)
    except Exception as exc:
        await message.answer(f"Failed to load listings: {exc}")
        return
    if not items:
        await message.answer("No listings found", reply_markup=_main_menu_keyboard())
        return
    has_more = len(items) > LISTINGS_PAGE_SIZE
    if has_more:
        items = items[:LISTINGS_PAGE_SIZE]
    lines = []
    if page > 0 or has_more:
        lines.append(f"Page: {page + 1}")
    for item in items:
        price = item.get("price_usd")
        price_label = "-" if price is None else price
        lines.append(
            f"#{item.get('id')} channel={item.get('channel_id')} price={price_label} format={item.get('format')}"
        )
    text = "\n".join(lines)
    markup = _items_keyboard(
        items, LISTING_PREFIX, page=page, has_more=has_more, page_prefix=LISTINGS_PAGE_PREFIX
    )
    if edit:
        try:
            await message.edit_text(text, reply_markup=markup)
        except TelegramBadRequest:
            await message.answer(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


async def _send_requests(message: Message, state: FSMContext, *, edit: bool = False) -> None:
    data = await state.get_data()
    page = max(int(data.get(REQUEST_LIST_PAGE_KEY) or 0), 0)
    limit = REQUESTS_PAGE_SIZE + 1
    offset = page * REQUESTS_PAGE_SIZE
    try:
        items = await api_client.list_requests(limit=limit, offset=offset)
    except Exception as exc:
        await message.answer(f"Failed to load requests: {exc}")
        return
    if not items:
        await message.answer("No requests found", reply_markup=_main_menu_keyboard())
        return
    has_more = len(items) > REQUESTS_PAGE_SIZE
    if has_more:
        items = items[:REQUESTS_PAGE_SIZE]
    lines = []
    if page > 0 or has_more:
        lines.append(f"Page: {page + 1}")
    for item in items:
        budget = item.get("budget")
        budget_label = "-" if budget is None else budget
        brief = item.get("brief") or ""
        lines.append(f"#{item.get('id')} budget={budget_label} brief={brief}")
    text = "\n".join(lines)
    markup = _items_keyboard(
        items, REQUEST_PREFIX, page=page, has_more=has_more, page_prefix=REQUESTS_PAGE_PREFIX
    )
    if edit:
        try:
            await message.edit_text(text, reply_markup=markup)
        except TelegramBadRequest:
            await message.answer(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


def _deal_quick_action(item: dict, role: str) -> tuple[str, str] | None:
    from bot.app.handlers.deals import DEAL_CREATIVE_PREFIX, DEAL_PAYMENT_PREFIX, DEAL_TERMS_PREFIX, ROLE_ADVERTISER, ROLE_OWNER

    deal_id = item.get("id")
    status = (item.get("status") or "").upper()
    if not deal_id:
        return None
    if role == ROLE_ADVERTISER and status in {"TERMS_LOCKED", "AWAITING_PAYMENT"}:
        return ("Payment", f"{DEAL_PAYMENT_PREFIX}{deal_id}")
    if role == ROLE_OWNER and status in {"NEGOTIATING", "TERMS_LOCKED"}:
        return ("Terms", f"{DEAL_TERMS_PREFIX}{deal_id}")
    if role == ROLE_OWNER and status in {"FUNDED", "CREATIVE_DRAFT"}:
        return ("Creative", f"{DEAL_CREATIVE_PREFIX}{deal_id}")
    return None


def _deals_keyboard(
    items: list[dict],
    roles_by_id: dict[int, str],
    filters: dict,
    *,
    has_more: bool,
    active_id: int | None,
):
    from bot.app.handlers.deals import DEAL_PREFIX

    status_group = filters.get("status_group") or "all"
    role_filter = filters.get("role") or "all"
    channel_id = filters.get("channel_id")
    page = max(int(filters.get("page") or 0), 0)
    status_label = _deal_status_label(status_group)
    role_label = _deal_role_label(role_filter)
    channel_label = _deal_channel_label(channel_id)
    next_status = _cycle_value(status_group, DEAL_STATUS_GROUP_ORDER)
    next_role = _cycle_value(role_filter, DEAL_ROLE_OPTIONS)
    builder = InlineKeyboardBuilder()
    for item in items:
        deal_id = item.get("id")
        if deal_id is None:
            continue
        label = f"#{deal_id}"
        if active_id == deal_id:
            label = f"{label} [active]"
        row = [InlineKeyboardButton(text=f"Open {label}", callback_data=f"{DEAL_PREFIX}{deal_id}")]
        role = roles_by_id.get(deal_id, "advertiser")
        quick_action = _deal_quick_action(item, role)
        if quick_action:
            row.append(InlineKeyboardButton(text=quick_action[0], callback_data=quick_action[1]))
        builder.row(*row)
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="Prev", callback_data=f"{DEALS_PAGE_PREFIX}{page - 1}"))
    if has_more:
        nav_buttons.append(InlineKeyboardButton(text="Next", callback_data=f"{DEALS_PAGE_PREFIX}{page + 1}"))
    if nav_buttons:
        builder.row(*nav_buttons)
    builder.row(
        InlineKeyboardButton(text=f"Status: {status_label}", callback_data=f"{DEALS_STATUS_PREFIX}{next_status}"),
        InlineKeyboardButton(text=f"Role: {role_label}", callback_data=f"{DEALS_ROLE_PREFIX}{next_role}"),
    )
    builder.row(
        InlineKeyboardButton(text=f"Channel: {channel_label}", callback_data=DEALS_CHANNEL_PREFIX),
        InlineKeyboardButton(text="Reset", callback_data=DEALS_CLEAR_PREFIX),
    )
    if active_id:
        builder.row(InlineKeyboardButton(text="Clear active", callback_data=DEALS_ACTIVE_CLEAR_PREFIX))
    builder.row(InlineKeyboardButton(text="Menu", callback_data=MENU_MAIN))
    return builder.as_markup()


async def _send_deals(message: Message, state: FSMContext, tg_user_id: int | None = None, *, edit: bool = False) -> None:
    user_id = tg_user_id if tg_user_id is not None else message.from_user.id
    filters = await _get_deal_filters(state)
    status_group = filters.get("status_group") or "all"
    role_filter = filters.get("role") or "all"
    channel_id = filters.get("channel_id")
    page = max(int(filters.get("page") or 0), 0)
    statuses = _deal_statuses_for_group(status_group)
    role_param = None if role_filter == "all" else role_filter
    limit = DEALS_PAGE_SIZE + 1
    offset = page * DEALS_PAGE_SIZE
    try:
        items = await api_client.list_deals(
            user_id,
            statuses=statuses,
            role=role_param,
            channel_id=channel_id,
            limit=limit,
            offset=offset,
            order_by=DEALS_ORDER_BY,
        )
    except Exception as exc:
        await message.answer(f"Failed to load deals: {exc}")
        return
    if not items:
        await message.answer("No deals found", reply_markup=_main_menu_keyboard())
        return
    has_more = len(items) > DEALS_PAGE_SIZE
    if has_more:
        items = items[:DEALS_PAGE_SIZE]
    try:
        channels = await api_client.list_channels(user_id)
    except Exception:
        channels = []
    channel_ids = {item.get("id") for item in channels if item.get("id") is not None}
    roles_by_id: dict[int, str] = {}
    for item in items:
        deal_id = item.get("id")
        if deal_id is None:
            continue
        if item.get("channel_id") in channel_ids:
            roles_by_id[deal_id] = "owner"
        else:
            roles_by_id[deal_id] = "advertiser"
    data = await state.get_data()
    active_id = data.get(ACTIVE_DEAL_KEY)
    lines = []
    if active_id:
        lines.append(f"Active deal: #{active_id}")
    status_label = _deal_status_label(status_group)
    role_label = _deal_role_label(role_filter)
    channel_label = _deal_channel_label(channel_id)
    lines.append(f"Filters: status={status_label} role={role_label} channel={channel_label}")
    if page > 0 or has_more:
        lines.append(f"Page: {page + 1}")
    from bot.app.handlers.deals import _next_step_for_role
    for item in items:
        deal_id = item.get("id")
        if deal_id is None:
            continue
        status = item.get("status")
        role = roles_by_id.get(deal_id, "advertiser")
        next_step = _next_step_for_role((status or "").upper(), role) if status else None
        price = item.get("price")
        price_label = "-" if price is None else price
        prefix = "[active] " if active_id == deal_id else ""
        line = f"{prefix}#{deal_id} status={status} channel={item.get('channel_id')} price={price_label}"
        if next_step:
            line = f"{line} next={next_step}"
        lines.append(line)
    text = "\n".join(lines)
    markup = _deals_keyboard(items, roles_by_id, filters, has_more=has_more, active_id=active_id)
    if edit:
        try:
            await message.edit_text(text, reply_markup=markup)
        except TelegramBadRequest:
            await message.answer(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


@router.message(Command("menu"))
@router.message(CommandTextFilter("menu"))
async def show_menu(message: Message) -> None:
    await message.answer("Choose an action:", reply_markup=await _main_menu_for_user(message.from_user.id))


@router.message(Command("wallet"))
@router.message(CommandTextFilter("wallet"))
async def set_wallet(message: Message, state: FSMContext) -> None:
    if await state.get_state():
        await state.clear()
    await state.set_state(WalletState.address)
    await _prompt_wallet(message)


@router.message(Command("cancel"))
async def cancel_flow(message: Message, state: FSMContext) -> None:
    if await state.get_state():
        await _clear_state_keep(state)
    await message.answer("Canceled.", reply_markup=await _main_menu_for_user(message.from_user.id))
@router.message(Command("listings"))
async def list_listings(message: Message, state: FSMContext) -> None:
    await state.update_data(**{LISTING_LIST_PAGE_KEY: 0})
    await _send_listings(message, state)


@router.message(Command("requests"))
async def list_requests(message: Message, state: FSMContext) -> None:
    await state.update_data(**{REQUEST_LIST_PAGE_KEY: 0})
    await _send_requests(message, state)


@router.message(Command("channels"))
async def list_channels(message: Message) -> None:
    try:
        items = await api_client.list_channels(message.from_user.id)
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


@router.message(Command("assigned_channels"))
async def list_assigned_channels(message: Message) -> None:
    try:
        auth = await api_client.auth_bot(message.from_user.id)
    except Exception as exc:
        await message.answer(f"Failed to load user: {exc}")
        return
    user = auth.get("user") if isinstance(auth, dict) else None
    user_id = user.get("id") if isinstance(user, dict) else None
    if user_id is None:
        await message.answer("User not found.")
        return
    try:
        items = await api_client.list_channels(message.from_user.id)
    except Exception as exc:
        await message.answer(f"Failed to load channels: {exc}")
        return
    assigned = [item for item in items if item.get("owner_user_id") != user_id]
    if not assigned:
        await message.answer("No assigned channels found", reply_markup=_main_menu_keyboard())
        return
    lines = []
    for item in assigned[:10]:
        username = item.get("username") or "-"
        title = item.get("title") or "-"
        lines.append(
            f"#{item.get('id')} tg_chat_id={item.get('tg_chat_id')} username={username} title={title}"
        )
    if len(assigned) > 10:
        lines.append(f"... {len(assigned) - 10} more")
    await message.answer("\n".join(lines), reply_markup=_main_menu_keyboard())


@router.message(Command("list_managers"))
async def list_managers(message: Message, state: FSMContext, bot: Bot) -> None:
    parts = (message.text or "").split()
    if len(parts) >= 2:
        channel_id = await _resolve_channel_id(message, bot, parts[1])
        if channel_id is None:
            return
        await _send_managers(message, channel_id)
        return
    await state.set_state(ManagerListState.channel_id)
    await _prompt_manager_channel_select(message, message.from_user.id, "list")


@router.message(Command("add_manager"))
async def add_manager(message: Message, state: FSMContext, bot: Bot) -> None:
    parts = (message.text or "").split()
    if len(parts) >= 3:
        channel_id = await _resolve_channel_id(message, bot, parts[1])
        if channel_id is None:
            return
        await _add_manager_by_username(message, channel_id, parts[2])
        return
    await state.set_state(ManagerAddState.channel_id)
    await _prompt_manager_channel_select(message, message.from_user.id, "add")


@router.message(Command("remove_manager"))
async def remove_manager(message: Message, state: FSMContext, bot: Bot) -> None:
    parts = (message.text or "").split()
    if len(parts) >= 3:
        channel_id = await _resolve_channel_id(message, bot, parts[1])
        if channel_id is None:
            return
        await _prepare_remove_manager(message, state, channel_id, parts[2])
        return
    await state.set_state(ManagerRemoveState.channel_id)
    await _prompt_manager_channel_select(message, message.from_user.id, "remove")


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
        deal = await api_client.create_deal(payload)
        await message.answer(f"Deal created: #{deal.get('id')}", reply_markup=_main_menu_keyboard())
    except Exception as exc:
        await message.answer(f"Failed to create deal: {exc}")


@router.message(Command("deals"))
async def list_deals(message: Message, state: FSMContext) -> None:
    await _send_deals(message, state)


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
        await api_client.create_request(payload)
        await message.answer("Request created", reply_markup=_main_menu_keyboard())
    except Exception as exc:
        await message.answer(f"Failed to create request: {exc}")


@router.message(Command("create_listing"))
async def create_listing(message: Message, state: FSMContext, bot: Bot) -> None:
    if not await _check_wallet(message, message.from_user.id):
        return
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
        await api_client.create_listing(payload)
        await message.answer("Listing created", reply_markup=_main_menu_keyboard())
    except Exception as exc:
        await message.answer(f"Failed to create listing: {exc}")


@router.callback_query(F.data == MENU_MAIN)
async def menu_main(callback: CallbackQuery) -> None:
    if callback.message:
        await callback.message.answer("Choose an action:", reply_markup=await _main_menu_for_user(callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data == MENU_LISTINGS)
async def menu_listings(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message:
        await state.update_data(**{LISTING_LIST_PAGE_KEY: 0})
        await _send_listings(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == MENU_REQUESTS)
async def menu_requests(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message:
        await state.update_data(**{REQUEST_LIST_PAGE_KEY: 0})
        await _send_requests(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == MENU_DEALS)
async def menu_deals(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message:
        await _send_deals(callback.message, state, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data.startswith(DEALS_PAGE_PREFIX))
async def deals_page(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    page_raw = callback.data[len(DEALS_PAGE_PREFIX) :]
    if not page_raw.isdigit():
        await callback.answer()
        return
    page = int(page_raw)
    await _set_deal_filters(state, page=page)
    await _send_deals(callback.message, state, callback.from_user.id, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith(LISTINGS_PAGE_PREFIX))
async def listings_page(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    page_raw = callback.data[len(LISTINGS_PAGE_PREFIX) :]
    if not page_raw.isdigit():
        await callback.answer()
        return
    page = int(page_raw)
    await state.update_data(**{LISTING_LIST_PAGE_KEY: page})
    await _send_listings(callback.message, state, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith(REQUESTS_PAGE_PREFIX))
async def requests_page(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    page_raw = callback.data[len(REQUESTS_PAGE_PREFIX) :]
    if not page_raw.isdigit():
        await callback.answer()
        return
    page = int(page_raw)
    await state.update_data(**{REQUEST_LIST_PAGE_KEY: page})
    await _send_requests(callback.message, state, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith(DEALS_STATUS_PREFIX))
async def deals_status_filter(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    group = callback.data[len(DEALS_STATUS_PREFIX) :]
    if group not in DEAL_STATUS_GROUPS:
        group = "all"
    await _set_deal_filters(state, status_group=group, page=0)
    await _send_deals(callback.message, state, callback.from_user.id, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith(DEALS_ROLE_PREFIX))
async def deals_role_filter(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    role = callback.data[len(DEALS_ROLE_PREFIX) :]
    if role not in DEAL_ROLE_OPTIONS:
        role = "all"
    await _set_deal_filters(state, role=role, page=0)
    await _send_deals(callback.message, state, callback.from_user.id, edit=True)
    await callback.answer()


@router.callback_query(F.data == DEALS_CHANNEL_PREFIX)
async def deals_channel_filter(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        await callback.answer()
        return
    await state.set_state(DealListFilterState.channel_id)
    await callback.message.answer("Enter channel_id for filter or 0 to reset.")
    await callback.answer()


@router.callback_query(F.data == DEALS_CLEAR_PREFIX)
async def deals_clear_filter(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        await callback.answer()
        return
    await state.update_data(**{DEAL_LIST_FILTERS_KEY: _default_deal_filters()})
    await _send_deals(callback.message, state, callback.from_user.id, edit=True)
    await callback.answer()


@router.callback_query(F.data == DEALS_ACTIVE_CLEAR_PREFIX)
async def deals_active_clear(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        await callback.answer()
        return
    from bot.app.handlers.deals import _clear_active_deal

    await _clear_active_deal(callback.message, state)
    await callback.message.answer("Active deal cleared.")
    await _send_deals(callback.message, state, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == MENU_CREATE_LISTING)
async def menu_create_listing(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message and not await _check_wallet(callback.message, callback.from_user.id):
        await callback.answer()
        return
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


@router.callback_query(F.data == MENU_WALLET)
async def menu_wallet(callback: CallbackQuery, state: FSMContext) -> None:
    if await state.get_state():
        await state.clear()
    await state.set_state(WalletState.address)
    if callback.message:
        await _prompt_wallet(callback.message)
    await callback.answer()


@router.callback_query(F.data.startswith(FLOW_BACK_PREFIX))
async def flow_back(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    _, flow, step = callback.data.split(":", 2)
    if step == "menu":
        if await state.get_state():
            await _clear_state_keep(state)
        await callback.message.answer("Choose an action:", reply_markup=await _main_menu_for_user(callback.from_user.id))
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
        await _clear_state_keep(state)
    await callback.message.answer("Canceled.", reply_markup=await _main_menu_for_user(callback.from_user.id))
    await callback.answer()


@router.message(WalletState.address)
async def wallet_address(message: Message, state: FSMContext) -> None:
    value = _strip_quotes(message.text or "").strip()
    if not value:
        await message.answer("Wallet address is required.")
        return
    payload = {"actor_tg_user_id": message.from_user.id, "linked_wallet": value}
    try:
        await api_client.update_wallet(message.from_user.id, payload)
        await message.answer("Wallet updated", reply_markup=_main_menu_keyboard(has_wallet=True))
    except Exception as exc:
        await message.answer(f"Failed to update wallet: {exc}")
        return
    await state.clear()


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


@router.callback_query(F.data.startswith(MANAGER_CHANNEL_PREFIX))
async def manager_channel_selected(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    data = callback.data[len(MANAGER_CHANNEL_PREFIX) :]
    if ":" not in data:
        await callback.answer()
        return
    flow, channel_raw = data.split(":", 1)
    try:
        channel_id = int(channel_raw)
    except ValueError:
        await callback.answer()
        return
    if flow == "add":
        await state.set_state(ManagerAddState.username)
        await state.update_data(channel_id=channel_id)
        await _prompt_manager_username(callback.message)
    if flow == "list":
        if await state.get_state():
            await _clear_state_keep(state)
        await _send_managers(callback.message, channel_id)
    if flow == "remove":
        await state.set_state(ManagerRemoveState.username)
        await state.update_data(channel_id=channel_id)
        await _prompt_manager_username(callback.message)
    await callback.answer()


@router.callback_query(F.data.startswith(MANAGER_CHANNEL_MANUAL))
async def manager_channel_manual(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    _, flow = callback.data.split(":", 1)
    if flow == "add":
        await state.set_state(ManagerAddState.channel_id)
    if flow == "list":
        await state.set_state(ManagerListState.channel_id)
    if flow == "remove":
        await state.set_state(ManagerRemoveState.channel_id)
    await _prompt_manager_channel_manual(callback.message)
    await callback.answer()


@router.callback_query(F.data.startswith(MANAGER_REMOVE_CONFIRM_PREFIX))
async def manager_remove_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    data = callback.data[len(MANAGER_REMOVE_CONFIRM_PREFIX) :]
    if ":" not in data:
        await callback.answer()
        return
    channel_raw, manager_raw = data.split(":", 1)
    try:
        channel_id = int(channel_raw)
        manager_id = int(manager_raw)
    except ValueError:
        await callback.answer()
        return
    try:
        await api_client.remove_channel_manager(callback.from_user.id, channel_id, manager_id)
    except Exception as exc:
        await callback.message.answer(f"Failed to remove manager: {exc}")
        await callback.answer()
        return
    if await state.get_state():
        await _clear_state_keep(state)
    await callback.message.answer("Manager removed.", reply_markup=_main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith(LISTING_PREFIX))
async def listing_details(callback: CallbackQuery) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    listing_id = int(callback.data.split(":", 1)[1])
    try:
        listing = await api_client.get_listing(listing_id)
    except Exception as exc:
        await callback.message.answer(f"Failed to load listing: {exc}")
        await callback.answer()
        return
    is_own = False
    try:
        channels = await api_client.list_channels(callback.from_user.id)
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
        listing = await api_client.get_listing(listing_id)
    except Exception as exc:
        await callback.message.answer(f"Failed to load listing: {exc}")
        await callback.answer()
        return
    if not listing.get("active", True):
        await callback.message.answer("Listing is inactive.", reply_markup=_main_menu_keyboard())
        await callback.answer()
        return
    try:
        channels = await api_client.list_channels(callback.from_user.id)
    except Exception as exc:
        await callback.message.answer(f"Failed to load channels: {exc}")
        await callback.answer()
        return
    if any(item.get("id") == listing.get("channel_id") for item in channels):
        await callback.message.answer("You cannot respond to your own listing.", reply_markup=_main_menu_keyboard())
        await callback.answer()
        return
    init_data: dict = {"listing_id": listing_id}
    listing_price = listing.get("price_usd")
    listing_format = listing.get("format")
    if listing_price is not None:
        init_data["price_usd"] = float(listing_price)
    if listing_format:
        init_data["format"] = listing_format
    await state.update_data(**init_data)
    if listing_price is None:
        await state.set_state(ListingRespondState.price_usd)
        await _prompt_listing_respond_price(callback.message)
    elif not listing_format:
        await state.set_state(ListingRespondState.format)
        await _prompt_listing_respond_format(callback.message)
    else:
        await state.set_state(ListingRespondState.brief)
        await _prompt_listing_respond_brief(callback.message)
    await callback.answer()


@router.callback_query(F.data.startswith(REQUEST_PREFIX))
async def request_details(callback: CallbackQuery) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    request_id = int(callback.data.split(":", 1)[1])
    try:
        request_item = await api_client.get_request(request_id)
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
        await api_client.create_listing(payload)
        await message.answer("Listing created", reply_markup=_main_menu_keyboard())
    except Exception as exc:
        await message.answer(f"Failed to create listing: {exc}")
    await _clear_state_keep(state)


@router.message(ManagerAddState.channel_id)
async def manager_add_channel_id(message: Message, state: FSMContext, bot: Bot) -> None:
    value = (message.text or "").strip()
    channel_id = await _resolve_channel_id(message, bot, value)
    if channel_id is None:
        return
    await state.update_data(channel_id=channel_id)
    await state.set_state(ManagerAddState.username)
    await _prompt_manager_username(message)


@router.message(ManagerAddState.username)
async def manager_add_username(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    channel_id = data.get("channel_id")
    if channel_id is None:
        await message.answer("Channel not found.", reply_markup=_main_menu_keyboard())
        await _clear_state_keep(state)
        return
    added = await _add_manager_by_username(message, int(channel_id), message.text or "")
    if added:
        await _clear_state_keep(state)


@router.message(ManagerListState.channel_id)
async def manager_list_channel_id(message: Message, state: FSMContext, bot: Bot) -> None:
    value = (message.text or "").strip()
    channel_id = await _resolve_channel_id(message, bot, value)
    if channel_id is None:
        return
    await _send_managers(message, channel_id)
    await _clear_state_keep(state)


@router.message(ManagerRemoveState.channel_id)
async def manager_remove_channel_id(message: Message, state: FSMContext, bot: Bot) -> None:
    value = (message.text or "").strip()
    channel_id = await _resolve_channel_id(message, bot, value)
    if channel_id is None:
        return
    await state.update_data(channel_id=channel_id)
    await state.set_state(ManagerRemoveState.username)
    await _prompt_manager_username(message)


@router.message(ManagerRemoveState.username)
async def manager_remove_username(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    channel_id = data.get("channel_id")
    if channel_id is None:
        await message.answer("Channel not found.", reply_markup=_main_menu_keyboard())
        await _clear_state_keep(state)
        return
    await _prepare_remove_manager(message, state, int(channel_id), message.text or "")


@router.message(DealListFilterState.channel_id)
async def deal_filter_channel_id(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if not value:
        await message.answer("Enter channel_id or 0 to reset.")
        return
    if not value.isdigit():
        await message.answer("Channel_id must be a number.")
        return
    channel_value = int(value)
    channel_id = None if channel_value == 0 else channel_value
    await _set_deal_filters(state, channel_id=channel_id, page=0)
    await _clear_state_keep(state)
    await _send_deals(message, state)


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
    data = await state.get_data()
    if data.get("format"):
        await state.set_state(ListingRespondState.brief)
        await _prompt_listing_respond_brief(message)
    else:
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
    await state.update_data(brief=brief_value)
    await state.set_state(ListingRespondState.publish_at)
    await _prompt_listing_respond_publish_at(message, state=state)


@router.message(ListingRespondState.publish_at)
async def listing_respond_publish_at(message: Message, state: FSMContext) -> None:
    import re

    value = (message.text or "").strip()
    if _is_skip(value):
        await state.update_data(publish_at=None)
    else:
        normalized = value.replace("Z", "+00:00")
        parsed = None
        try:
            datetime.fromisoformat(normalized)
            parsed = normalized
        except ValueError:
            pass
        if not parsed:
            m = re.match(r"^(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?\s+(\d{1,2}):(\d{2})$", value)
            if m:
                day, month = int(m.group(1)), int(m.group(2))
                year = int(m.group(3)) if m.group(3) else datetime.now().year
                hour, minute = int(m.group(4)), int(m.group(5))
                try:
                    dt = datetime(year, month, day, hour, minute)
                    parsed = dt.strftime("%Y-%m-%dT%H:%M:%S+03:00")
                except ValueError:
                    pass
        if not parsed:
            await message.answer("Invalid format. Use the calendar or enter: 15.02 18:30")
            return
        await state.update_data(publish_at=parsed)
    await state.set_state(ListingRespondState.creative)
    await _prompt_listing_respond_creative(message)


@router.message(ListingRespondState.creative)
async def listing_respond_creative(message: Message, state: FSMContext) -> None:
    text = None
    skip_requested = False
    if message.text:
        text = message.text
    if message.caption:
        text = message.caption
    media_file_ids = None
    if message.photo:
        media_file_ids = [{"type": "photo", "file_id": message.photo[-1].file_id}]
    if message.video:
        media_file_ids = [{"type": "video", "file_id": message.video.file_id}]
    if message.animation:
        media_file_ids = [{"type": "animation", "file_id": message.animation.file_id}]
    if message.document:
        media_file_ids = [{"type": "document", "file_id": message.document.file_id}]
    if text and _is_skip(text):
        if not media_file_ids:
            skip_requested = True
        text = None
    if not text and not media_file_ids and not skip_requested:
        await message.answer("Send text/media or 'skip'.")
        return
    data = await state.get_data()
    listing_id = data.get("listing_id")
    if listing_id is None:
        await message.answer("Listing not found.", reply_markup=_main_menu_keyboard())
        await _clear_state_keep(state)
        return
    try:
        listing = await api_client.get_listing(int(listing_id))
    except Exception as exc:
        await message.answer(f"Failed to load listing: {exc}")
        await _clear_state_keep(state)
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
        "brief": data.get("brief"),
        "publish_at": data.get("publish_at"),
    }
    try:
        deal = await api_client.create_deal(payload)
        deal_id = int(deal.get("id"))
        brief_lines = []
        if data.get("brief"):
            brief_lines.append(f"brief: {data.get('brief')}")
        if text:
            brief_lines.append(f"creative_example: {text}")
        brief_text = "\n".join(brief_lines) if brief_lines else None
        if brief_text or data.get("publish_at") or media_file_ids:
            try:
                await api_client.create_advertiser_brief(
                    deal_id,
                    {
                        "actor_tg_user_id": message.from_user.id,
                        "text": brief_text,
                        "publish_at": data.get("publish_at"),
                        "media_file_ids": media_file_ids,
                    },
                )
            except Exception:
                pass
        await message.answer(f"Deal created: #{deal.get('id')}")
        try:
            from bot.app.handlers.deals import _send_deal_details
        except Exception:
            await message.answer("Use /deal to open the deal.", reply_markup=_main_menu_keyboard())
            await _clear_state_keep(state)
            return
        await _send_deal_details(message, deal_id, state=state, set_active=True)
    except Exception as exc:
        await message.answer(f"Failed to create deal: {exc}")
    await _clear_state_keep(state)


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
        await api_client.create_request(payload)
        await message.answer("Request created", reply_markup=_main_menu_keyboard())
    except Exception as exc:
        await message.answer(f"Failed to create request: {exc}")
    await _clear_state_keep(state)
