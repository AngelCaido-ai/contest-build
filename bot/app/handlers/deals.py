from datetime import datetime

from aiogram import F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.app.services import api_client

router = Router()

DEAL_PREFIX = "deal:"
DEAL_TERMS_PREFIX = "deal_terms:"
DEAL_TERMS_BACK_PREFIX = "deal_terms_back:"
DEAL_TERMS_CANCEL_PREFIX = "deal_terms_cancel:"
DEAL_STATUS_PREFIX = "deal_status:"
DEAL_STATUS_SET_PREFIX = "deal_status_set:"
DEAL_STATUS_BACK_PREFIX = "deal_status_back:"
DEAL_STATUS_CANCEL_PREFIX = "deal_status_cancel:"
DEAL_CREATIVE_PREFIX = "deal_creative:"
DEAL_CREATIVE_BACK_PREFIX = "deal_creative_back:"
DEAL_CREATIVE_CANCEL_PREFIX = "deal_creative_cancel:"
DEAL_CREATIVE_STATUS_PREFIX = "deal_creative_status:"
DEAL_CREATIVE_STATUS_SET_PREFIX = "deal_creative_status_set:"
DEAL_CREATIVE_STATUS_BACK_PREFIX = "deal_creative_status_back:"
DEAL_CREATIVE_STATUS_CANCEL_PREFIX = "deal_creative_status_cancel:"

DEAL_STATUSES = {
    "NEGOTIATING",
    "TERMS_LOCKED",
    "AWAITING_PAYMENT",
    "FUNDED",
    "CREATIVE_DRAFT",
    "CREATIVE_REVIEW",
    "APPROVED",
    "SCHEDULED",
    "POSTED",
    "VERIFYING",
    "RELEASED",
    "REFUNDED",
    "CANCELED",
}

CREATIVE_STATUSES = {"DRAFT", "REVIEW", "APPROVED"}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "NEGOTIATING": {"TERMS_LOCKED", "CANCELED"},
    "TERMS_LOCKED": {"AWAITING_PAYMENT", "CREATIVE_DRAFT", "CANCELED"},
    "AWAITING_PAYMENT": {"FUNDED", "CANCELED"},
    "FUNDED": {"CREATIVE_DRAFT", "CANCELED"},
    "CREATIVE_DRAFT": {"CREATIVE_REVIEW", "CANCELED"},
    "CREATIVE_REVIEW": {"APPROVED", "CANCELED"},
    "APPROVED": {"SCHEDULED", "CANCELED"},
    "SCHEDULED": {"POSTED", "CANCELED"},
    "POSTED": {"VERIFYING"},
    "VERIFYING": {"RELEASED", "REFUNDED"},
}

STATUS_ORDER = [
    "TERMS_LOCKED",
    "AWAITING_PAYMENT",
    "FUNDED",
    "CREATIVE_DRAFT",
    "CREATIVE_REVIEW",
    "APPROVED",
    "SCHEDULED",
    "POSTED",
    "VERIFYING",
    "RELEASED",
    "REFUNDED",
    "CANCELED",
]


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


class DealTermsState(StatesGroup):
    price = State()
    publish_at = State()
    verification_window = State()
    format = State()


class DealStatusState(StatesGroup):
    status = State()


class CreativeState(StatesGroup):
    content = State()


class CreativeStatusState(StatesGroup):
    status = State()


CREATIVE_STATUS_ORDER = ["DRAFT", "REVIEW", "APPROVED"]


def _sorted_statuses(statuses: set[str]) -> list[str]:
    order = {status: index for index, status in enumerate(STATUS_ORDER)}
    return sorted(statuses, key=lambda status: order.get(status, 999))


def _status_label(status: str, options: list[str]) -> str:
    if status == "CANCELED":
        if len(options) == 2 and "CANCELED" in options:
            return "Отклонить"
        return "Отменить сделку"
    if len(options) == 2 and "CANCELED" in options:
        return "Принять"
    return status


def _nav_keyboard(back_data: str | None, cancel_data: str):
    builder = InlineKeyboardBuilder()
    if back_data:
        builder.button(text="Назад", callback_data=back_data)
    builder.button(text="Отмена", callback_data=cancel_data)
    builder.adjust(2)
    return builder.as_markup()


def _terms_keyboard(deal_id: int, back_step: str | None):
    back_data = None if back_step is None else f"{DEAL_TERMS_BACK_PREFIX}{deal_id}:{back_step}"
    cancel_data = f"{DEAL_TERMS_CANCEL_PREFIX}{deal_id}"
    return _nav_keyboard(back_data, cancel_data)


def _status_keyboard(deal_id: int, statuses: set[str]):
    options = _sorted_statuses(statuses)
    builder = InlineKeyboardBuilder()
    for status in options:
        builder.button(text=_status_label(status, options), callback_data=f"{DEAL_STATUS_SET_PREFIX}{deal_id}:{status}")
    builder.button(text="Назад", callback_data=f"{DEAL_STATUS_BACK_PREFIX}{deal_id}")
    builder.button(text="Отмена", callback_data=f"{DEAL_STATUS_CANCEL_PREFIX}{deal_id}")
    builder.adjust(2)
    return builder.as_markup()


def _creative_status_keyboard(deal_id: int):
    builder = InlineKeyboardBuilder()
    for status in CREATIVE_STATUS_ORDER:
        builder.button(text=status, callback_data=f"{DEAL_CREATIVE_STATUS_SET_PREFIX}{deal_id}:{status}")
    builder.button(text="Назад", callback_data=f"{DEAL_CREATIVE_STATUS_BACK_PREFIX}{deal_id}")
    builder.button(text="Отмена", callback_data=f"{DEAL_CREATIVE_STATUS_CANCEL_PREFIX}{deal_id}")
    builder.adjust(2)
    return builder.as_markup()


def _deal_actions_keyboard(deal: dict):
    deal_id = deal.get("id")
    status = (deal.get("status") or "").upper()
    builder = InlineKeyboardBuilder()
    if status in {"NEGOTIATING", "TERMS_LOCKED"}:
        builder.button(text="Update terms", callback_data=f"{DEAL_TERMS_PREFIX}{deal_id}")
    if status in {"TERMS_LOCKED", "FUNDED"}:
        builder.button(text="Create creative", callback_data=f"{DEAL_CREATIVE_PREFIX}{deal_id}")
    if status in {"CREATIVE_DRAFT", "CREATIVE_REVIEW"}:
        builder.button(text="Creative status", callback_data=f"{DEAL_CREATIVE_STATUS_PREFIX}{deal_id}")
    if status in ALLOWED_TRANSITIONS and ALLOWED_TRANSITIONS[status]:
        builder.button(text="Change status", callback_data=f"{DEAL_STATUS_PREFIX}{deal_id}")
    builder.button(text="Back to deals", callback_data="menu:deals")
    builder.button(text="Back to menu", callback_data="menu:main")
    builder.adjust(2)
    return builder.as_markup()


def _deal_text(deal: dict) -> str:
    return "\n".join(
        [
            f"Deal #{deal.get('id')}",
            f"status: {deal.get('status')}",
            f"listing_id: {deal.get('listing_id')}",
            f"request_id: {deal.get('request_id')}",
            f"channel_id: {deal.get('channel_id')}",
            f"price: {deal.get('price')}",
            f"format: {deal.get('format')}",
            f"publish_at: {deal.get('publish_at')}",
            f"verification_window: {deal.get('verification_window')}",
            f"tampered: {deal.get('tampered')}",
            f"deleted: {deal.get('deleted')}",
        ]
    )


def _normalize_datetime(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    datetime.fromisoformat(normalized)
    return text


async def _prompt_terms_price(message: Message, deal_id: int) -> None:
    await message.answer("Enter price.", reply_markup=_terms_keyboard(deal_id, "details"))


async def _prompt_terms_publish_at(message: Message, deal_id: int) -> None:
    await message.answer("Enter publish_at in ISO format.", reply_markup=_terms_keyboard(deal_id, "price"))


async def _prompt_terms_verification_window(message: Message, deal_id: int) -> None:
    await message.answer("Enter verification window in minutes.", reply_markup=_terms_keyboard(deal_id, "publish_at"))


async def _prompt_terms_format(message: Message, deal_id: int) -> None:
    await message.answer("Enter format or 'skip'.", reply_markup=_terms_keyboard(deal_id, "verification_window"))


async def _send_deal_details(message: Message, deal_id: int) -> None:
    try:
        deal = api_client.get_deal(deal_id)
    except Exception as exc:
        await message.answer(f"Failed to load deal: {exc}")
        return
    await message.answer(_deal_text(deal), reply_markup=_deal_actions_keyboard(deal))


@router.message(Command("deal"))
@router.message(CommandTextFilter("deal"))
async def deal_info(message: Message, state: FSMContext) -> None:
    if await state.get_state():
        await state.clear()
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /deal DEAL_ID")
        return
    deal_id = int(parts[1])
    await _send_deal_details(message, deal_id)


@router.callback_query(F.data.startswith(DEAL_PREFIX))
async def deal_details_callback(callback: CallbackQuery) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    deal_id = int(callback.data.split(":", 1)[1])
    await _send_deal_details(callback.message, deal_id)
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_TERMS_PREFIX))
async def deal_terms_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data:
        await callback.answer()
        return
    deal_id = int(callback.data.split(":", 1)[1])
    await state.update_data(deal_id=deal_id)
    await state.set_state(DealTermsState.price)
    if callback.message:
        await _prompt_terms_price(callback.message, deal_id)
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_TERMS_BACK_PREFIX))
async def deal_terms_back(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    _, deal_id_value, step = callback.data.split(":", 2)
    deal_id = int(deal_id_value)
    if step == "details":
        if await state.get_state():
            await state.clear()
        await _send_deal_details(callback.message, deal_id)
        await callback.answer()
        return
    await state.update_data(deal_id=deal_id)
    if step == "price":
        await state.set_state(DealTermsState.price)
        await _prompt_terms_price(callback.message, deal_id)
    if step == "publish_at":
        await state.set_state(DealTermsState.publish_at)
        await _prompt_terms_publish_at(callback.message, deal_id)
    if step == "verification_window":
        await state.set_state(DealTermsState.verification_window)
        await _prompt_terms_verification_window(callback.message, deal_id)
    if step == "format":
        await state.set_state(DealTermsState.format)
        await _prompt_terms_format(callback.message, deal_id)
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_TERMS_CANCEL_PREFIX))
async def deal_terms_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    deal_id = int(callback.data.split(":", 1)[1])
    if await state.get_state():
        await state.clear()
    await _send_deal_details(callback.message, deal_id)
    await callback.answer()


@router.message(DealTermsState.price)
async def deal_terms_price(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    try:
        price = float(value)
    except ValueError:
        await message.answer("Price must be a number.")
        return
    await state.update_data(price=price)
    await state.set_state(DealTermsState.publish_at)
    data = await state.get_data()
    deal_id = data["deal_id"]
    await _prompt_terms_publish_at(message, deal_id)


@router.message(DealTermsState.publish_at)
async def deal_terms_publish_at(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    try:
        publish_at = _normalize_datetime(value)
    except ValueError:
        await message.answer("Invalid datetime. Use ISO format.")
        return
    if not publish_at:
        await message.answer("Publish_at is required.")
        return
    await state.update_data(publish_at=publish_at)
    await state.set_state(DealTermsState.verification_window)
    data = await state.get_data()
    deal_id = data["deal_id"]
    await _prompt_terms_verification_window(message, deal_id)


@router.message(DealTermsState.verification_window)
async def deal_terms_verification_window(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if not value.isdigit():
        await message.answer("Verification window must be a number.")
        return
    await state.update_data(verification_window=int(value))
    await state.set_state(DealTermsState.format)
    data = await state.get_data()
    deal_id = data["deal_id"]
    await _prompt_terms_format(message, deal_id)


@router.message(DealTermsState.format)
async def deal_terms_format(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    format_value = None if value.lower() in {"skip", "-"} else value
    data = await state.get_data()
    payload = {
        "price": data["price"],
        "publish_at": data["publish_at"],
        "verification_window": data["verification_window"],
        "format": format_value or "post",
    }
    try:
        api_client.update_terms(data["deal_id"], payload)
        await message.answer("Terms updated")
    except Exception as exc:
        await message.answer(f"Failed to update terms: {exc}")
    await state.clear()
    await _send_deal_details(message, data["deal_id"])


@router.callback_query(F.data.startswith(DEAL_STATUS_PREFIX))
async def deal_status_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data:
        await callback.answer()
        return
    deal_id = int(callback.data.split(":", 1)[1])
    try:
        deal = api_client.get_deal(deal_id)
    except Exception as exc:
        if callback.message:
            await callback.message.answer(f"Failed to load deal: {exc}")
        await callback.answer()
        return
    status = (deal.get("status") or "").upper()
    allowed = ALLOWED_TRANSITIONS.get(status, set())
    await state.update_data(deal_id=deal_id)
    await state.set_state(DealStatusState.status)
    if callback.message:
        if not allowed:
            await callback.message.answer(
                "No available status transitions.",
                reply_markup=_nav_keyboard(
                    f"{DEAL_STATUS_BACK_PREFIX}{deal_id}",
                    f"{DEAL_STATUS_CANCEL_PREFIX}{deal_id}",
                ),
            )
        else:
            await callback.message.answer("Select new status.", reply_markup=_status_keyboard(deal_id, allowed))
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_STATUS_SET_PREFIX))
async def deal_status_set(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    _, deal_id_value, status_value = callback.data.split(":", 2)
    deal_id = int(deal_id_value)
    try:
        api_client.update_status(deal_id, status_value)
        await callback.message.answer("Status updated")
    except Exception as exc:
        await callback.message.answer(f"Failed to update status: {exc}")
    if await state.get_state():
        await state.clear()
    await _send_deal_details(callback.message, deal_id)
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_STATUS_BACK_PREFIX))
async def deal_status_back(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    deal_id = int(callback.data.split(":", 1)[1])
    if await state.get_state():
        await state.clear()
    await _send_deal_details(callback.message, deal_id)
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_STATUS_CANCEL_PREFIX))
async def deal_status_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    deal_id = int(callback.data.split(":", 1)[1])
    if await state.get_state():
        await state.clear()
    await _send_deal_details(callback.message, deal_id)
    await callback.answer()


@router.message(DealStatusState.status)
async def deal_status_value(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip().upper()
    if value not in DEAL_STATUSES:
        await message.answer("Unknown status.")
        return
    data = await state.get_data()
    deal_id = data.get("deal_id")
    if deal_id is None:
        await message.answer("Deal is required.")
        return
    try:
        deal = api_client.get_deal(deal_id)
    except Exception as exc:
        await message.answer(f"Failed to load deal: {exc}")
        return
    current = (deal.get("status") or "").upper()
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if not allowed:
        await message.answer("No available status transitions.")
        return
    if value not in allowed:
        await message.answer("Status transition is not allowed.")
        return
    try:
        api_client.update_status(deal_id, value)
        await message.answer("Status updated")
    except Exception as exc:
        await message.answer(f"Failed to update status: {exc}")
    await state.clear()
    await _send_deal_details(message, deal_id)


@router.callback_query(F.data.startswith(DEAL_CREATIVE_PREFIX))
async def deal_creative_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data:
        await callback.answer()
        return
    deal_id = int(callback.data.split(":", 1)[1])
    await state.update_data(deal_id=deal_id)
    await state.set_state(CreativeState.content)
    if callback.message:
        await callback.message.answer(
            "Send creative text or attach media.",
            reply_markup=_nav_keyboard(
                f"{DEAL_CREATIVE_BACK_PREFIX}{deal_id}",
                f"{DEAL_CREATIVE_CANCEL_PREFIX}{deal_id}",
            ),
        )
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_CREATIVE_BACK_PREFIX))
async def deal_creative_back(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    deal_id = int(callback.data.split(":", 1)[1])
    if await state.get_state():
        await state.clear()
    await _send_deal_details(callback.message, deal_id)
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_CREATIVE_CANCEL_PREFIX))
async def deal_creative_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    deal_id = int(callback.data.split(":", 1)[1])
    if await state.get_state():
        await state.clear()
    await _send_deal_details(callback.message, deal_id)
    await callback.answer()


@router.message(CreativeState.content)
async def deal_creative_content(message: Message, state: FSMContext) -> None:
    text = None
    if message.text:
        text = message.text
    if message.caption:
        text = message.caption
    media_file_ids = None
    if message.photo:
        media_file_ids = [message.photo[-1].file_id]
    if message.document:
        media_file_ids = [message.document.file_id]
    if not text and not media_file_ids:
        await message.answer("Send text or media.")
        return
    data = await state.get_data()
    payload = {"text": text, "media_file_ids": media_file_ids}
    try:
        api_client.create_creative(data["deal_id"], payload)
        await message.answer("Creative drafted")
    except Exception as exc:
        await message.answer(f"Failed to create creative: {exc}")
    await state.clear()
    await _send_deal_details(message, data["deal_id"])


@router.callback_query(F.data.startswith(DEAL_CREATIVE_STATUS_PREFIX))
async def deal_creative_status_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data:
        await callback.answer()
        return
    deal_id = int(callback.data.split(":", 1)[1])
    await state.update_data(deal_id=deal_id)
    await state.set_state(CreativeStatusState.status)
    if callback.message:
        await callback.message.answer(
            "Select creative status.",
            reply_markup=_creative_status_keyboard(deal_id),
        )
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_CREATIVE_STATUS_SET_PREFIX))
async def deal_creative_status_set(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    _, deal_id_value, status_value = callback.data.split(":", 2)
    deal_id = int(deal_id_value)
    try:
        api_client.update_creative_status(deal_id, status_value)
        await callback.message.answer("Creative status updated")
    except Exception as exc:
        await callback.message.answer(f"Failed to update creative status: {exc}")
    if await state.get_state():
        await state.clear()
    await _send_deal_details(callback.message, deal_id)
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_CREATIVE_STATUS_BACK_PREFIX))
async def deal_creative_status_back(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    deal_id = int(callback.data.split(":", 1)[1])
    if await state.get_state():
        await state.clear()
    await _send_deal_details(callback.message, deal_id)
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_CREATIVE_STATUS_CANCEL_PREFIX))
async def deal_creative_status_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    deal_id = int(callback.data.split(":", 1)[1])
    if await state.get_state():
        await state.clear()
    await _send_deal_details(callback.message, deal_id)
    await callback.answer()


@router.message(CreativeStatusState.status)
async def deal_creative_status_value(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip().upper()
    if value not in CREATIVE_STATUSES:
        await message.answer("Unknown creative status.")
        return
    data = await state.get_data()
    try:
        api_client.update_creative_status(data["deal_id"], value)
        await message.answer("Creative status updated")
    except Exception as exc:
        await message.answer(f"Failed to update creative status: {exc}")
    await state.clear()
    await _send_deal_details(message, data["deal_id"])


@router.message(Command("terms"))
@router.message(CommandTextFilter("terms"))
async def set_terms(message: Message, state: FSMContext) -> None:
    if await state.get_state():
        await state.clear()
    parts = (message.text or "").split()
    if len(parts) < 5:
        await message.answer("Usage: /terms DEAL_ID PRICE PUBLISH_AT ISO VERIFICATION_MINUTES [FORMAT]")
        return
    deal_id = int(parts[1])
    price = float(parts[2])
    publish_at = parts[3]
    verification_window = int(parts[4])
    format_value = parts[5] if len(parts) > 5 else "post"
    payload = {
        "price": price,
        "publish_at": publish_at,
        "verification_window": verification_window,
        "format": format_value,
    }
    try:
        api_client.update_terms(deal_id, payload)
        await message.answer("Terms updated")
    except Exception as exc:
        await message.answer(f"Failed to update terms: {exc}")


@router.message(Command("status"))
@router.message(CommandTextFilter("status"))
async def set_status(message: Message, state: FSMContext) -> None:
    if await state.get_state():
        await state.clear()
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer("Usage: /status DEAL_ID STATUS")
        return
    deal_id = int(parts[1])
    status_value = parts[2]
    try:
        api_client.update_status(deal_id, status_value)
        await message.answer("Status updated")
    except Exception as exc:
        await message.answer(f"Failed to update status: {exc}")


@router.message(Command("creative"))
@router.message(CommandTextFilter("creative"))
async def create_creative(message: Message, state: FSMContext) -> None:
    if await state.get_state():
        await state.clear()
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2:
        await message.answer("Usage: /creative DEAL_ID [TEXT]")
        return
    deal_id = int(parts[1])
    text = parts[2] if len(parts) > 2 else None
    media_file_ids = None
    if message.photo:
        media_file_ids = [message.photo[-1].file_id]
    if message.document:
        media_file_ids = [message.document.file_id]
    payload = {"text": text, "media_file_ids": media_file_ids}
    try:
        api_client.create_creative(deal_id, payload)
        await message.answer("Creative drafted")
    except Exception as exc:
        await message.answer(f"Failed to create creative: {exc}")


@router.message(Command("creative_status"))
@router.message(CommandTextFilter("creative_status"))
async def creative_status(message: Message, state: FSMContext) -> None:
    if await state.get_state():
        await state.clear()
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer("Usage: /creative_status DEAL_ID STATUS")
        return
    deal_id = int(parts[1])
    status_value = parts[2]
    try:
        api_client.update_creative_status(deal_id, status_value)
        await message.answer("Creative status updated")
    except Exception as exc:
        await message.answer(f"Failed to update creative status: {exc}")


@router.message(F.text)
async def fallback_commands(message: Message) -> None:
    command = _extract_command(message.text)
    if command == "deal":
        await deal_info(message)
        return
    if command == "terms":
        await set_terms(message)
        return
    if command == "status":
        await set_status(message)
        return
    if command == "creative":
        await create_creative(message)
        return
    if command == "creative_status":
        await creative_status(message)
