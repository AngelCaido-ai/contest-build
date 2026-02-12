import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import quote, urlencode

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InputMediaAnimation,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.app.services import api_client

logger = logging.getLogger(__name__)
router = Router()

DEAL_PREFIX = "deal:"
DEAL_TERMS_PREFIX = "deal_terms:"
DEAL_TERMS_BACK_PREFIX = "deal_terms_back:"
DEAL_TERMS_CANCEL_PREFIX = "deal_terms_cancel:"
DEAL_STATUS_PREFIX = "deal_status:"
DEAL_STATUS_SET_PREFIX = "deal_status_set:"
DEAL_STATUS_BACK_PREFIX = "deal_status_back:"
DEAL_STATUS_CANCEL_PREFIX = "deal_status_cancel:"
DEAL_PAYMENT_PREFIX = "deal_payment:"
DEAL_CREATIVE_PREFIX = "deal_creative:"
DEAL_CREATIVE_BACK_PREFIX = "deal_creative_back:"
DEAL_CREATIVE_CANCEL_PREFIX = "deal_creative_cancel:"
DEAL_PUBLISH_AT_PREFIX = "deal_publish_at:"
DEAL_PUBLISH_AT_BACK_PREFIX = "deal_publish_at_back:"
DEAL_PUBLISH_AT_CANCEL_PREFIX = "deal_publish_at_cancel:"
DEAL_CREATIVE_STATUS_PREFIX = "deal_creative_status:"
DEAL_CREATIVE_STATUS_SET_PREFIX = "deal_creative_status_set:"
DEAL_CREATIVE_STATUS_BACK_PREFIX = "deal_creative_status_back:"
DEAL_CREATIVE_STATUS_CANCEL_PREFIX = "deal_creative_status_cancel:"
DEAL_CREATIVE_VIEW_PREFIX = "deal_creative_view:"
DEAL_CREATIVE_PREVIOUS_PREFIX = "deal_creative_previous:"
DEAL_MESSAGE_PREFIX = "deal_msg:"
DEAL_MESSAGE_BACK_PREFIX = "deal_msg_back:"
DEAL_MESSAGE_CANCEL_PREFIX = "deal_msg_cancel:"
DEAL_MESSAGE_HISTORY_PREFIX = "deal_msg_history:"
DEAL_SWITCH_PREFIX = "deal_switch:"
DEAL_DRAFT_RESUME_PREFIX = "deal_draft_resume:"
DEAL_DRAFT_CLEAR_PREFIX = "deal_draft_clear:"

ACTIVE_DEAL_KEY = "active_deal_id"
ACTIVE_DEAL_PIN_KEY = "active_deal_pinned_message_id"
DEAL_DRAFTS_KEY = "deal_drafts"
DEAL_LIST_FILTERS_KEY = "deal_list_filters"
SWITCH_FROM_STATE_KEY = "switch_from_state"
SWITCH_FROM_DEAL_KEY = "switch_from_deal_id"
SWITCH_TARGET_DEAL_KEY = "switch_target_deal_id"

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

ROLE_OWNER = "owner"
ROLE_ADVERTISER = "advertiser"

ROLE_ALLOWED_STATUSES: dict[str, set[str]] = {
    ROLE_OWNER: {
        "TERMS_LOCKED",
        "CANCELED",
        "SCHEDULED",
        "POSTED",
        "VERIFYING",
        "RELEASED",
        "REFUNDED",
    },
    ROLE_ADVERTISER: {
        "AWAITING_PAYMENT",
        "FUNDED",
        "CANCELED",
    },
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


class DealPublishAtState(StatesGroup):
    publish_at = State()


class CreativeState(StatesGroup):
    content = State()


class CreativeStatusState(StatesGroup):
    status = State()
    comment = State()
    publish_at = State()


CREATIVE_STATUS_ORDER = ["DRAFT", "REVIEW", "APPROVED"]


class DealMessageState(StatesGroup):
    content = State()


class DealSwitchState(StatesGroup):
    confirm = State()


PERSISTENT_STATE_KEYS = {
    ACTIVE_DEAL_KEY,
    ACTIVE_DEAL_PIN_KEY,
    DEAL_DRAFTS_KEY,
    DEAL_LIST_FILTERS_KEY,
}
SWITCH_STATE_KEYS = {
    SWITCH_FROM_STATE_KEY,
    SWITCH_FROM_DEAL_KEY,
    SWITCH_TARGET_DEAL_KEY,
}
DEAL_FLOW_STATES = {
    DealTermsState.price.state,
    DealTermsState.publish_at.state,
    DealTermsState.verification_window.state,
    DealTermsState.format.state,
    DealStatusState.status.state,
    CreativeState.content.state,
    CreativeStatusState.status.state,
    CreativeStatusState.comment.state,
    CreativeStatusState.publish_at.state,
    DealMessageState.content.state,
}


def _sorted_statuses(statuses: set[str]) -> list[str]:
    order = {status: index for index, status in enumerate(STATUS_ORDER)}
    return sorted(statuses, key=lambda status: order.get(status, 999))


def _allowed_transitions_for_role(status: str, role: str) -> set[str]:
    allowed = ALLOWED_TRANSITIONS.get(status, set())
    role_allowed = ROLE_ALLOWED_STATUSES.get(role, set())
    return allowed & role_allowed


def _resolve_deal_role(tg_user_id: int, deal: dict) -> str:
    channel_id = deal.get("channel_id")
    try:
        channels = api_client.list_channels(tg_user_id)
    except Exception:
        return ROLE_ADVERTISER
    if any(item.get("id") == channel_id for item in channels):
        return ROLE_OWNER
    return ROLE_ADVERTISER


def _next_step_for_role(status: str, role: str) -> str | None:
    if status == "NEGOTIATING":
        return "Lock terms or cancel the deal." if role == ROLE_OWNER else "Wait for owner to lock terms."
    if status == "TERMS_LOCKED":
        return "Wait for payment." if role == ROLE_OWNER else "Pay escrow (Payment details)."
    if status == "AWAITING_PAYMENT":
        return "Wait for payment." if role == ROLE_OWNER else "Send payment to escrow."
    if status == "FUNDED":
        return "Create and submit creative." if role == ROLE_OWNER else "Wait for creative."
    if status == "CREATIVE_DRAFT":
        return "Update creative and submit for review." if role == ROLE_OWNER else "Wait for creative."
    if status == "CREATIVE_REVIEW":
        return "Review creative and approve/request edits." if role == ROLE_ADVERTISER else "Waiting for review."
    if status == "APPROVED":
        return "Schedule the post." if role == ROLE_OWNER else "Waiting for schedule."
    if status == "SCHEDULED":
        return "Post at scheduled time." if role == ROLE_OWNER else "Waiting for post."
    if status == "POSTED":
        return "Start verification." if role == ROLE_OWNER else "Waiting for verification."
    if status == "VERIFYING":
        return "Release or refund after verification window." if role == ROLE_OWNER else "Waiting for release/refund."
    return None


async def _clear_state_keep(state: FSMContext, keep_keys: set[str] | None = None) -> dict:
    data = await state.get_data()
    keys = keep_keys or PERSISTENT_STATE_KEYS
    keep = {key: data[key] for key in keys if key in data}
    await state.clear()
    if keep:
        await state.update_data(**keep)
    return keep


def _draft_payload(data: dict) -> dict:
    return {key: value for key, value in data.items() if key not in PERSISTENT_STATE_KEYS | SWITCH_STATE_KEYS}


def _get_drafts(data: dict) -> dict:
    drafts = data.get(DEAL_DRAFTS_KEY)
    if isinstance(drafts, dict):
        return drafts
    return {}


async def _save_deal_draft(state: FSMContext, deal_id: int, state_name: str, flow_data: dict) -> None:
    data = await state.get_data()
    drafts = _get_drafts(data)
    drafts[str(deal_id)] = {"state": state_name, "data": flow_data}
    await state.update_data(**{DEAL_DRAFTS_KEY: drafts})


async def _clear_deal_draft(state: FSMContext, deal_id: int) -> None:
    data = await state.get_data()
    drafts = _get_drafts(data)
    if str(deal_id) in drafts:
        drafts.pop(str(deal_id), None)
        await state.update_data(**{DEAL_DRAFTS_KEY: drafts})


async def _get_deal_draft(state: FSMContext, deal_id: int) -> dict | None:
    data = await state.get_data()
    drafts = _get_drafts(data)
    return drafts.get(str(deal_id))


def _active_deal_text(deal: dict, role: str, draft_available: bool) -> str:
    header = "Активная сделка"
    if draft_available:
        header = f"{header} (черновик)"
    return f"{header}\n{_deal_text(deal, role)}"


def _switch_keyboard(target_deal_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="Сохранить черновик и перейти", callback_data=f"{DEAL_SWITCH_PREFIX}save:{target_deal_id}")
    builder.button(text="Сбросить и перейти", callback_data=f"{DEAL_SWITCH_PREFIX}discard:{target_deal_id}")
    builder.button(text="Отмена", callback_data=f"{DEAL_SWITCH_PREFIX}cancel:{target_deal_id}")
    builder.adjust(1)
    return builder.as_markup()


async def _update_active_deal_pin(
    message: Message,
    state: FSMContext,
    deal: dict,
    role: str,
    draft_available: bool,
    creative_version: int | None = None,
) -> None:
    data = await state.get_data()
    pinned_id = data.get(ACTIVE_DEAL_PIN_KEY)
    text = _active_deal_text(deal, role, draft_available)
    reply_markup = _deal_actions_keyboard(
        deal,
        role,
        creative_version=creative_version,
        draft_available=draft_available,
    )
    bot = message.bot
    chat_id = message.chat.id
    updated = False
    if pinned_id:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=int(pinned_id),
                text=text,
                reply_markup=reply_markup,
            )
            updated = True
        except TelegramBadRequest:
            updated = False
    if not updated:
        pinned_message = await message.answer(text, reply_markup=reply_markup)
        try:
            await bot.pin_chat_message(chat_id, pinned_message.message_id, disable_notification=True)
        except TelegramBadRequest:
            pass
        await state.update_data(**{ACTIVE_DEAL_PIN_KEY: pinned_message.message_id})


async def _set_active_deal(
    message: Message,
    state: FSMContext,
    deal: dict,
    role: str,
    draft_available: bool,
    creative_version: int | None = None,
) -> None:
    await state.update_data(**{ACTIVE_DEAL_KEY: deal.get("id")})
    await _update_active_deal_pin(message, state, deal, role, draft_available, creative_version)


async def _refresh_active_deal_pin(
    message: Message,
    state: FSMContext,
    deal: dict,
    role: str,
    draft_available: bool,
    creative_version: int | None = None,
) -> None:
    data = await state.get_data()
    if data.get(ACTIVE_DEAL_KEY) == deal.get("id"):
        await _update_active_deal_pin(message, state, deal, role, draft_available, creative_version)


async def _clear_active_deal(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    pinned_id = data.get(ACTIVE_DEAL_PIN_KEY)
    await state.update_data(**{ACTIVE_DEAL_KEY: None, ACTIVE_DEAL_PIN_KEY: None})
    if pinned_id:
        try:
            await message.bot.unpin_chat_message(message.chat.id, int(pinned_id))
        except TelegramBadRequest:
            pass


async def _maybe_prompt_deal_switch(
    message: Message,
    state: FSMContext,
    target_deal_id: int,
) -> bool:
    current_state = await state.get_state()
    if not current_state or current_state == DealSwitchState.confirm.state:
        return False
    if current_state not in DEAL_FLOW_STATES:
        return False
    data = await state.get_data()
    active_deal_id = data.get(ACTIVE_DEAL_KEY)
    if not active_deal_id or active_deal_id == target_deal_id:
        return False
    current_deal_id = data.get("deal_id") or active_deal_id
    if not current_deal_id:
        return False
    await state.update_data(
        **{
            SWITCH_FROM_STATE_KEY: current_state,
            SWITCH_FROM_DEAL_KEY: current_deal_id,
            SWITCH_TARGET_DEAL_KEY: target_deal_id,
        }
    )
    await state.set_state(DealSwitchState.confirm)
    await message.answer(
        f"Есть незавершенный шаг по сделке #{current_deal_id}. Перейти к сделке #{target_deal_id}?",
        reply_markup=_switch_keyboard(target_deal_id),
    )
    return True


def _state_by_name(value: str) -> State | None:
    mapping = {
        DealTermsState.price.state: DealTermsState.price,
        DealTermsState.publish_at.state: DealTermsState.publish_at,
        DealTermsState.verification_window.state: DealTermsState.verification_window,
        DealTermsState.format.state: DealTermsState.format,
        DealStatusState.status.state: DealStatusState.status,
        CreativeState.content.state: CreativeState.content,
        CreativeStatusState.status.state: CreativeStatusState.status,
        CreativeStatusState.comment.state: CreativeStatusState.comment,
        CreativeStatusState.publish_at.state: CreativeStatusState.publish_at,
        DealMessageState.content.state: DealMessageState.content,
    }
    return mapping.get(value)


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


def _creative_status_keyboard(deal_id: int, statuses: list[str]):
    builder = InlineKeyboardBuilder()
    for status in statuses:
        builder.button(text=status, callback_data=f"{DEAL_CREATIVE_STATUS_SET_PREFIX}{deal_id}:{status}")
    builder.button(text="Назад", callback_data=f"{DEAL_CREATIVE_STATUS_BACK_PREFIX}{deal_id}")
    builder.button(text="Отмена", callback_data=f"{DEAL_CREATIVE_STATUS_CANCEL_PREFIX}{deal_id}")
    builder.adjust(2)
    return builder.as_markup()


def _normalize_media_items(media_items: list[dict] | list[str] | None) -> list[dict]:
    normalized: list[dict] = []
    for item in media_items or []:
        if isinstance(item, dict):
            file_id = item.get("file_id")
            media_type = item.get("type") or "document"
        elif isinstance(item, str):
            file_id = item
            media_type = "photo"
        else:
            continue
        if not file_id:
            continue
        if media_type not in {"photo", "document", "video", "animation"}:
            media_type = "document"
        normalized.append({"type": media_type, "media": file_id})
    return normalized


async def _send_creative_preview(message: Message, creative: dict) -> None:
    text = creative.get("text")
    media_items = _normalize_media_items(creative.get("media_file_ids"))
    if not media_items:
        if text:
            await message.answer(text)
        return
    if len(media_items) == 1:
        media = media_items[0]
        if media["type"] == "photo":
            await message.answer_photo(media["media"], caption=text)
            return
        if media["type"] == "video":
            await message.answer_video(media["media"], caption=text)
            return
        if media["type"] == "animation":
            await message.answer_animation(media["media"], caption=text)
            return
        await message.answer_document(media["media"], caption=text)
        return
    group = []
    for index, media in enumerate(media_items):
        caption = text if index == 0 else None
        if media["type"] == "photo":
            group.append(InputMediaPhoto(media["media"], caption=caption))
        elif media["type"] == "video":
            group.append(InputMediaVideo(media["media"], caption=caption))
        elif media["type"] == "animation":
            group.append(InputMediaAnimation(media["media"], caption=caption))
        else:
            group.append(InputMediaDocument(media["media"], caption=caption))
    await message.answer_media_group(media=group)


def _deal_actions_keyboard(
    deal: dict,
    role: str,
    creative_version: int | None = None,
    draft_available: bool = False,
):
    deal_id = deal.get("id")
    status = (deal.get("status") or "").upper()
    publish_at = deal.get("publish_at")
    allowed_statuses = _allowed_transitions_for_role(status, role)
    builder = InlineKeyboardBuilder()
    if draft_available:
        builder.button(text="Продолжить черновик", callback_data=f"{DEAL_DRAFT_RESUME_PREFIX}{deal_id}")
        builder.button(text="Сбросить черновик", callback_data=f"{DEAL_DRAFT_CLEAR_PREFIX}{deal_id}")
    if role == ROLE_OWNER and status in {"NEGOTIATING", "TERMS_LOCKED"}:
        builder.button(text="Update terms", callback_data=f"{DEAL_TERMS_PREFIX}{deal_id}")
    if role == ROLE_ADVERTISER and status in {"TERMS_LOCKED", "AWAITING_PAYMENT"}:
        builder.button(text="Payment details", callback_data=f"{DEAL_PAYMENT_PREFIX}{deal_id}")
    if role == ROLE_OWNER and status in {"FUNDED", "CREATIVE_DRAFT"}:
        builder.button(text="Create creative", callback_data=f"{DEAL_CREATIVE_PREFIX}{deal_id}")
    if role == ROLE_ADVERTISER and status in {"CREATIVE_REVIEW"}:
        builder.button(text="Creative status", callback_data=f"{DEAL_CREATIVE_STATUS_PREFIX}{deal_id}")
    if role in {ROLE_ADVERTISER, ROLE_OWNER} and status not in {"RELEASED", "REFUNDED", "CANCELED"}:
        builder.button(text="Написать сообщение", callback_data=f"{DEAL_MESSAGE_PREFIX}{deal_id}")
        builder.button(text="История переписки", callback_data=f"{DEAL_MESSAGE_HISTORY_PREFIX}{deal_id}")
    if (
        role == ROLE_OWNER
        and not publish_at
        and status not in {"NEGOTIATING", "TERMS_LOCKED", "POSTED", "VERIFYING", "RELEASED", "REFUNDED", "CANCELED"}
    ):
        builder.button(text="Set publish time", callback_data=f"{DEAL_PUBLISH_AT_PREFIX}{deal_id}")
    view_statuses = {
        "CREATIVE_REVIEW",
        "CREATIVE_DRAFT",
        "APPROVED",
        "SCHEDULED",
        "POSTED",
        "VERIFYING",
        "RELEASED",
    }
    if role in {ROLE_ADVERTISER, ROLE_OWNER} and status in view_statuses:
        builder.button(text="View creative", callback_data=f"{DEAL_CREATIVE_VIEW_PREFIX}{deal_id}")
    if role == ROLE_OWNER and creative_version and creative_version > 1 and status in view_statuses:
        builder.button(
            text="View previous creative",
            callback_data=f"{DEAL_CREATIVE_PREVIOUS_PREFIX}{deal_id}:{creative_version - 1}",
        )
    if allowed_statuses:
        builder.button(text="Change status", callback_data=f"{DEAL_STATUS_PREFIX}{deal_id}")
    builder.button(text="Back to deals", callback_data="menu:deals")
    builder.button(text="Back to menu", callback_data="menu:main")
    builder.adjust(2)
    return builder.as_markup()


def _deal_text(deal: dict, role: str) -> str:
    status = (deal.get("status") or "").upper()
    lines = [
        f"Deal #{deal.get('id')}",
        f"status: {deal.get('status')}",
        f"listing_id: {deal.get('listing_id')}",
        f"request_id: {deal.get('request_id')}",
        f"channel_id: {deal.get('channel_id')}",
        f"price: {deal.get('price')}",
        f"format: {deal.get('format')}",
        f"brief: {deal.get('brief')}",
        f"publish_at: {deal.get('publish_at')}",
        f"verification_window: {deal.get('verification_window')}",
        f"posted_message_id: {deal.get('posted_message_id')}",
        f"tampered: {deal.get('tampered')}",
        f"deleted: {deal.get('deleted')}",
    ]
    next_step = _next_step_for_role(status, role)
    if next_step:
        lines.append(f"next_step: {next_step}")
    return "\n".join(lines)


def _normalize_datetime(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    datetime.fromisoformat(normalized)
    return text


def _format_message_time(value: str | None) -> str:
    if not value:
        return "-"
    normalized = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return value
    return dt.strftime("%d.%m %H:%M")


def _message_sender_label(value: str | None) -> str:
    if value == ROLE_ADVERTISER:
        return "Рекламодатель"
    if value == ROLE_OWNER:
        return "Владелец"
    return "Участник"


def _message_history_text(items: list[dict]) -> str:
    lines = ["История переписки:"]
    for item in items:
        payload = item.get("payload") or {}
        sender_role = payload.get("sender_role")
        sender = _message_sender_label(sender_role if isinstance(sender_role, str) else None)
        text_value = payload.get("text")
        text = text_value.strip() if isinstance(text_value, str) else ""
        media_items = payload.get("media_file_ids") or []
        if text and len(text) > 180:
            text = f"{text[:177]}..."
        if not text and media_items:
            text = "[медиа]"
        if not text:
            text = "[пусто]"
        lines.append(f"{_format_message_time(item.get('created_at'))} {sender}: {text}")
    return "\n".join(lines)


def _message_history_keyboard(deal_id: int, before_id: int | None, has_more: bool):
    builder = InlineKeyboardBuilder()
    builder.button(text="Ответить", callback_data=f"{DEAL_MESSAGE_PREFIX}{deal_id}")
    if has_more and before_id is not None:
        builder.button(text="Еще", callback_data=f"{DEAL_MESSAGE_HISTORY_PREFIX}{deal_id}:{before_id}")
    builder.button(text="К сделке", callback_data=f"{DEAL_PREFIX}{deal_id}")
    builder.button(text="К списку", callback_data="menu:deals")
    builder.adjust(2)
    return builder.as_markup()


async def _prompt_terms_price(message: Message, deal_id: int) -> None:
    await message.answer("Enter price.", reply_markup=_terms_keyboard(deal_id, "details"))


async def _prompt_terms_publish_at(message: Message, deal_id: int) -> None:
    await message.answer("Enter publish_at in ISO format.", reply_markup=_terms_keyboard(deal_id, "price"))


async def _prompt_terms_verification_window(message: Message, deal_id: int) -> None:
    await message.answer("Enter verification window in minutes.", reply_markup=_terms_keyboard(deal_id, "publish_at"))


async def _prompt_terms_format(message: Message, deal_id: int) -> None:
    await message.answer("Enter format or 'skip'.", reply_markup=_terms_keyboard(deal_id, "verification_window"))


async def _prompt_publish_at_only(message: Message, deal_id: int) -> None:
    await message.answer(
        "Enter publish_at in ISO format.",
        reply_markup=_nav_keyboard(
            f"{DEAL_PUBLISH_AT_BACK_PREFIX}{deal_id}",
            f"{DEAL_PUBLISH_AT_CANCEL_PREFIX}{deal_id}",
        ),
    )


async def _prompt_creative_status_comment(message: Message, deal_id: int) -> None:
    await message.answer(
        "Send comment for owner to update creative.",
        reply_markup=_nav_keyboard(
            f"{DEAL_CREATIVE_STATUS_BACK_PREFIX}{deal_id}",
            f"{DEAL_CREATIVE_STATUS_CANCEL_PREFIX}{deal_id}",
        ),
    )


async def _prompt_creative_status_publish_at(message: Message, deal_id: int) -> None:
    await message.answer(
        "Enter publish_at in ISO format.",
        reply_markup=_nav_keyboard(
            f"{DEAL_CREATIVE_STATUS_BACK_PREFIX}{deal_id}",
            f"{DEAL_CREATIVE_STATUS_CANCEL_PREFIX}{deal_id}",
        ),
    )


async def _prompt_deal_message(message: Message, deal_id: int) -> None:
    await message.answer(
        "Отправьте сообщение или медиа.",
        reply_markup=_nav_keyboard(
            f"{DEAL_MESSAGE_BACK_PREFIX}{deal_id}",
            f"{DEAL_MESSAGE_CANCEL_PREFIX}{deal_id}",
        ),
    )


async def _send_deal_details(
    message: Message,
    deal_id: int,
    tg_user_id: int | None = None,
    state: FSMContext | None = None,
    set_active: bool = False,
) -> None:
    try:
        deal = api_client.get_deal(deal_id)
    except Exception as exc:
        await message.answer(f"Failed to load deal: {exc}")
        return
    actor_id = tg_user_id if tg_user_id is not None else message.from_user.id
    role = _resolve_deal_role(actor_id, deal)
    creative_version = None
    status = (deal.get("status") or "").upper()
    if status in {
        "CREATIVE_REVIEW",
        "CREATIVE_DRAFT",
        "APPROVED",
        "SCHEDULED",
        "POSTED",
        "VERIFYING",
        "RELEASED",
    }:
        try:
            creative = api_client.get_creative(deal_id, actor_id)
            version_value = creative.get("version")
            if isinstance(version_value, int):
                creative_version = version_value
        except Exception:
            creative_version = None
    draft_available = False
    if state:
        draft_available = await _get_deal_draft(state, deal_id) is not None
    if not (state and set_active):
        await message.answer(
            _deal_text(deal, role),
            reply_markup=_deal_actions_keyboard(
                deal,
                role,
                creative_version=creative_version,
                draft_available=draft_available,
            ),
        )
    if state:
        if set_active:
            await _set_active_deal(message, state, deal, role, draft_available, creative_version)
        else:
            await _refresh_active_deal_pin(message, state, deal, role, draft_available, creative_version)


@router.callback_query(F.data.startswith(DEAL_SWITCH_PREFIX))
async def deal_switch_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    _, action, deal_id_value = callback.data.split(":", 2)
    try:
        target_deal_id = int(deal_id_value)
    except ValueError:
        await callback.answer()
        return
    data = await state.get_data()
    from_state = data.get(SWITCH_FROM_STATE_KEY)
    from_deal_id = data.get(SWITCH_FROM_DEAL_KEY)
    if action == "cancel":
        state_value = _state_by_name(from_state) if isinstance(from_state, str) else None
        if state_value:
            await state.set_state(state_value)
        else:
            await _clear_state_keep(state)
        await state.update_data(
            **{
                SWITCH_FROM_STATE_KEY: None,
                SWITCH_FROM_DEAL_KEY: None,
                SWITCH_TARGET_DEAL_KEY: None,
            }
        )
        await callback.answer()
        return
    if action == "save" and from_deal_id and isinstance(from_state, str):
        flow_data = _draft_payload(data)
        if "deal_id" not in flow_data:
            flow_data["deal_id"] = from_deal_id
        await _save_deal_draft(state, int(from_deal_id), from_state, flow_data)
    await _clear_state_keep(state)
    if action == "discard" and from_deal_id:
        await _clear_deal_draft(state, int(from_deal_id))
    await _send_deal_details(
        callback.message,
        target_deal_id,
        callback.from_user.id,
        state=state,
        set_active=True,
    )
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_DRAFT_RESUME_PREFIX))
async def deal_draft_resume(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    deal_id_value = callback.data.split(":", 1)[1]
    try:
        deal_id = int(deal_id_value)
    except ValueError:
        await callback.answer()
        return
    draft = await _get_deal_draft(state, deal_id)
    if not draft:
        await callback.message.answer("Черновик не найден.")
        await callback.answer()
        return
    draft_state = draft.get("state")
    draft_data = draft.get("data") or {}
    await _clear_state_keep(state)
    await state.update_data(**draft_data)
    state_value = _state_by_name(draft_state) if isinstance(draft_state, str) else None
    if not state_value:
        await callback.message.answer("Черновик недоступен.")
        await callback.answer()
        return
    await _clear_deal_draft(state, deal_id)
    await state.set_state(state_value)
    try:
        deal = api_client.get_deal(deal_id)
    except Exception as exc:
        await callback.message.answer(f"Failed to load deal: {exc}")
        await callback.answer()
        return
    role = _resolve_deal_role(callback.from_user.id, deal)
    creative_version = None
    status = (deal.get("status") or "").upper()
    if status in {
        "CREATIVE_REVIEW",
        "CREATIVE_DRAFT",
        "APPROVED",
        "SCHEDULED",
        "POSTED",
        "VERIFYING",
        "RELEASED",
    }:
        try:
            creative = api_client.get_creative(deal_id, callback.from_user.id)
            version_value = creative.get("version")
            if isinstance(version_value, int):
                creative_version = version_value
        except Exception:
            creative_version = None
    await _set_active_deal(callback.message, state, deal, role, False, creative_version)
    if draft_state == DealTermsState.price.state:
        await _prompt_terms_price(callback.message, deal_id)
    elif draft_state == DealTermsState.publish_at.state:
        await _prompt_terms_publish_at(callback.message, deal_id)
    elif draft_state == DealTermsState.verification_window.state:
        await _prompt_terms_verification_window(callback.message, deal_id)
    elif draft_state == DealTermsState.format.state:
        await _prompt_terms_format(callback.message, deal_id)
    elif draft_state == DealStatusState.status.state:
        allowed = _allowed_transitions_for_role(status, role)
        if not allowed:
            await callback.message.answer("No available status transitions.")
        else:
            await callback.message.answer("Select new status.", reply_markup=_status_keyboard(deal_id, allowed))
    elif draft_state == CreativeState.content.state:
        await callback.message.answer(
            "Send creative text or attach media.",
            reply_markup=_nav_keyboard(
                f"{DEAL_CREATIVE_BACK_PREFIX}{deal_id}",
                f"{DEAL_CREATIVE_CANCEL_PREFIX}{deal_id}",
            ),
        )
    elif draft_state == CreativeStatusState.status.state:
        await callback.message.answer(
            "Select creative status.",
            reply_markup=_creative_status_keyboard(deal_id, ["DRAFT", "APPROVED"]),
        )
    elif draft_state == CreativeStatusState.comment.state:
        await _prompt_creative_status_comment(callback.message, deal_id)
    elif draft_state == CreativeStatusState.publish_at.state:
        await _prompt_creative_status_publish_at(callback.message, deal_id)
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_DRAFT_CLEAR_PREFIX))
async def deal_draft_clear(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    deal_id_value = callback.data.split(":", 1)[1]
    try:
        deal_id = int(deal_id_value)
    except ValueError:
        await callback.answer()
        return
    await _clear_deal_draft(state, deal_id)
    await callback.message.answer("Черновик удален.")
    try:
        deal = api_client.get_deal(deal_id)
    except Exception:
        await callback.answer()
        return
    role = _resolve_deal_role(callback.from_user.id, deal)
    await _refresh_active_deal_pin(callback.message, state, deal, role, False)
    await callback.answer()


@router.message(Command("deal"))
@router.message(CommandTextFilter("deal"))
async def deal_info(message: Message, state: FSMContext) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /deal DEAL_ID")
        return
    try:
        deal_id = int(parts[1])
    except ValueError:
        await message.answer("Usage: /deal DEAL_ID")
        return
    if await _maybe_prompt_deal_switch(message, state, deal_id):
        return
    current_state = await state.get_state()
    if current_state and current_state not in DEAL_FLOW_STATES:
        await _clear_state_keep(state)
    await _send_deal_details(message, deal_id, state=state, set_active=True)


@router.callback_query(F.data.startswith(DEAL_PREFIX))
async def deal_details_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    deal_id = int(callback.data.split(":", 1)[1])
    if await _maybe_prompt_deal_switch(callback.message, state, deal_id):
        await callback.answer()
        return
    current_state = await state.get_state()
    if current_state and current_state not in DEAL_FLOW_STATES:
        await _clear_state_keep(state)
    await _send_deal_details(
        callback.message,
        deal_id,
        callback.from_user.id,
        state=state,
        set_active=True,
    )
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_PAYMENT_PREFIX))
async def deal_payment_details(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    deal_id = int(callback.data.split(":", 1)[1])
    try:
        deal = api_client.get_deal(deal_id)
    except Exception as exc:
        await callback.message.answer(f"Failed to load deal: {exc}")
        await callback.answer()
        return
    role = _resolve_deal_role(callback.from_user.id, deal)
    draft_available = await _get_deal_draft(state, deal_id) is not None
    await _set_active_deal(callback.message, state, deal, role, draft_available)
    try:
        payment = api_client.create_deposit(
            deal_id,
            {
                "actor_tg_user_id": callback.from_user.id,
                "expected_amount": deal.get("price"),
            },
        )
    except Exception as exc:
        await callback.message.answer(f"Failed to create deposit: {exc}")
        await callback.answer()
        return
    address = payment.get("deposit_address")
    comment = payment.get("deposit_comment")
    amount = payment.get("expected_amount")
    deal_price = deal.get("price")
    amount_nano = None
    if amount is not None:
        try:
            amount_nano = int(Decimal(str(amount)) * Decimal("1000000000"))
        except (InvalidOperation, ValueError):
            amount_nano = None
    lines = [
        "Escrow payment details:",
        f"address: {address}",
        f"comment: {comment}",
        f"amount: {amount}",
    ]
    if amount is not None and deal_price is not None:
        try:
            if Decimal(str(amount)) > Decimal(str(deal_price)):
                lines.append("amount includes reserve for fees.")
        except (InvalidOperation, ValueError):
            pass
    lines.append("Telegram Wallet does not support prefilled payments.")
    lines.append("After payment, wait for auto-detection or set status to FUNDED.")
    builder = InlineKeyboardBuilder()
    if address:
        ton_params = {}
        if amount_nano is not None:
            ton_params["amount"] = amount_nano
        if comment:
            ton_params["text"] = str(comment)
        ton_url = f"ton://transfer/{address}"
        if ton_params:
            ton_url = f"{ton_url}?{urlencode(ton_params)}"
        builder.button(text="Open TON wallet", url=ton_url)
        tk_params = {}
        if amount_nano is not None:
            tk_params["amount"] = amount_nano
        if comment:
            tk_params["text"] = str(comment)
        tonkeeper_url = f"https://app.tonkeeper.com/transfer/{address}"
        if tk_params:
            tonkeeper_url = f"{tonkeeper_url}?{urlencode(tk_params)}"
        builder.button(text="Open Tonkeeper", url=tonkeeper_url)
    builder.button(text="Open deal", callback_data=f"{DEAL_PREFIX}{deal_id}")
    builder.adjust(1)
    await callback.message.answer("\n".join(lines), reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_TERMS_PREFIX))
async def deal_terms_start(callback: CallbackQuery, state: FSMContext) -> None:
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
    role = _resolve_deal_role(callback.from_user.id, deal)
    if role != ROLE_OWNER:
        if callback.message:
            await callback.message.answer("Only channel owner can update terms.")
        await callback.answer()
        return
    draft_available = await _get_deal_draft(state, deal_id) is not None
    if callback.message:
        await _set_active_deal(callback.message, state, deal, role, draft_available)
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
            await _clear_state_keep(state)
        await _send_deal_details(callback.message, deal_id, callback.from_user.id, state=state)
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
        await _clear_state_keep(state)
    await _send_deal_details(callback.message, deal_id, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_PUBLISH_AT_PREFIX))
async def deal_publish_at_start(callback: CallbackQuery, state: FSMContext) -> None:
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
    role = _resolve_deal_role(callback.from_user.id, deal)
    if role != ROLE_OWNER:
        if callback.message:
            await callback.message.answer("Only channel owner can set publish time.")
        await callback.answer()
        return
    status = (deal.get("status") or "").upper()
    if status in {"POSTED", "VERIFYING", "RELEASED", "REFUNDED", "CANCELED"}:
        if callback.message:
            await callback.message.answer("Publish time cannot be updated for this deal.")
        await callback.answer()
        return
    await state.update_data(deal_id=deal_id)
    await state.set_state(DealPublishAtState.publish_at)
    if callback.message:
        await _prompt_publish_at_only(callback.message, deal_id)
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_PUBLISH_AT_BACK_PREFIX))
async def deal_publish_at_back(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    deal_id = int(callback.data.split(":", 1)[1])
    if await state.get_state():
        await _clear_state_keep(state)
    await _send_deal_details(callback.message, deal_id, callback.from_user.id, state=state)
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_PUBLISH_AT_CANCEL_PREFIX))
async def deal_publish_at_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    deal_id = int(callback.data.split(":", 1)[1])
    if await state.get_state():
        await _clear_state_keep(state)
    await _send_deal_details(callback.message, deal_id, callback.from_user.id, state=state)
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
        "actor_tg_user_id": message.from_user.id,
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
    await _clear_deal_draft(state, data["deal_id"])
    await _clear_state_keep(state)
    await _send_deal_details(message, data["deal_id"], state=state)


@router.message(DealPublishAtState.publish_at)
async def deal_publish_at_value(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    try:
        publish_at = _normalize_datetime(value)
    except ValueError:
        await message.answer("Неверный формат даты. Пример: 2026-02-05T18:30:00+03:00.")
        return
    if not publish_at:
        await message.answer("Время публикации обязательно.")
        return
    data = await state.get_data()
    payload = {"actor_tg_user_id": message.from_user.id, "publish_at": publish_at}
    try:
        api_client.update_publish_at(data["deal_id"], payload)
        await message.answer("Publish time updated")
    except Exception as exc:
        await message.answer(f"Failed to update publish time: {exc}")
    await _clear_state_keep(state)
    await _send_deal_details(message, data["deal_id"], state=state)


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
    role = _resolve_deal_role(callback.from_user.id, deal)
    allowed = _allowed_transitions_for_role(status, role)
    draft_available = await _get_deal_draft(state, deal_id) is not None
    if callback.message:
        await _set_active_deal(callback.message, state, deal, role, draft_available)
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
    status_value = status_value.upper()
    try:
        deal = api_client.get_deal(deal_id)
    except Exception as exc:
        await callback.message.answer(f"Failed to load deal: {exc}")
        await callback.answer()
        return
    current = (deal.get("status") or "").upper()
    role = _resolve_deal_role(callback.from_user.id, deal)
    allowed = _allowed_transitions_for_role(current, role)
    if not allowed:
        await callback.message.answer("No available status transitions.")
        await callback.answer()
        return
    if status_value not in allowed:
        await callback.message.answer("Status transition is not allowed.")
        await callback.answer()
        return
    try:
        api_client.update_status(
            deal_id,
            {"status": status_value, "actor_tg_user_id": callback.from_user.id},
        )
        await callback.message.answer("Status updated")
    except Exception as exc:
        await callback.message.answer(f"Failed to update status: {exc}")
    if await state.get_state():
        await _clear_state_keep(state)
    await _clear_deal_draft(state, deal_id)
    await _send_deal_details(callback.message, deal_id, callback.from_user.id, state=state)
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_STATUS_BACK_PREFIX))
async def deal_status_back(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    deal_id = int(callback.data.split(":", 1)[1])
    if await state.get_state():
        await _clear_state_keep(state)
    await _send_deal_details(callback.message, deal_id, callback.from_user.id, state=state)
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_STATUS_CANCEL_PREFIX))
async def deal_status_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    deal_id = int(callback.data.split(":", 1)[1])
    if await state.get_state():
        await _clear_state_keep(state)
    await _send_deal_details(callback.message, deal_id, callback.from_user.id, state=state)
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
    role = _resolve_deal_role(message.from_user.id, deal)
    allowed = _allowed_transitions_for_role(current, role)
    if not allowed:
        await message.answer("No available status transitions.")
        return
    if value not in allowed:
        await message.answer("Status transition is not allowed.")
        return
    try:
        api_client.update_status(
            deal_id,
            {"status": value, "actor_tg_user_id": message.from_user.id},
        )
        await message.answer("Status updated")
    except Exception as exc:
        await message.answer(f"Failed to update status: {exc}")
    await _clear_deal_draft(state, deal_id)
    await _clear_state_keep(state)
    await _send_deal_details(message, deal_id, state=state)


@router.callback_query(F.data.startswith(DEAL_MESSAGE_PREFIX))
async def deal_message_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    deal_id = int(callback.data.split(":", 1)[1])
    if await _maybe_prompt_deal_switch(callback.message, state, deal_id):
        await callback.answer()
        return
    try:
        deal = api_client.get_deal(deal_id)
    except Exception as exc:
        await callback.message.answer(f"Failed to load deal: {exc}")
        await callback.answer()
        return
    status = (deal.get("status") or "").upper()
    if status in {"RELEASED", "REFUNDED", "CANCELED"}:
        await callback.message.answer("Сделка завершена. Переписка недоступна.")
        await callback.answer()
        return
    role = _resolve_deal_role(callback.from_user.id, deal)
    draft_available = await _get_deal_draft(state, deal_id) is not None
    await _set_active_deal(callback.message, state, deal, role, draft_available)
    await state.update_data(deal_id=deal_id)
    await state.set_state(DealMessageState.content)
    await _prompt_deal_message(callback.message, deal_id)
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_MESSAGE_BACK_PREFIX))
async def deal_message_back(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    deal_id = int(callback.data.split(":", 1)[1])
    if await state.get_state():
        await _clear_state_keep(state)
    await _send_deal_details(callback.message, deal_id, callback.from_user.id, state=state)
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_MESSAGE_CANCEL_PREFIX))
async def deal_message_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    deal_id = int(callback.data.split(":", 1)[1])
    if await state.get_state():
        await _clear_state_keep(state)
    await _send_deal_details(callback.message, deal_id, callback.from_user.id, state=state)
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_MESSAGE_HISTORY_PREFIX))
async def deal_message_history(callback: CallbackQuery) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    payload = callback.data[len(DEAL_MESSAGE_HISTORY_PREFIX) :]
    if not payload:
        await callback.answer()
        return
    parts = payload.split(":", 1)
    try:
        deal_id = int(parts[0])
    except ValueError:
        await callback.answer()
        return
    before_id = None
    if len(parts) == 2 and parts[1]:
        try:
            before_id = int(parts[1])
        except ValueError:
            before_id = None
    try:
        items = api_client.list_deal_messages(
            deal_id,
            callback.from_user.id,
            limit=8,
            before_id=before_id,
        )
    except Exception as exc:
        await callback.message.answer(f"Failed to load messages: {exc}")
        await callback.answer()
        return
    if not items:
        await callback.message.answer(
            "Сообщений пока нет.",
            reply_markup=_message_history_keyboard(deal_id, None, False),
        )
        await callback.answer()
        return
    oldest_id = None
    first_id = items[0].get("id")
    if isinstance(first_id, int):
        oldest_id = first_id
    has_more = len(items) >= 8 and oldest_id is not None
    await callback.message.answer(
        _message_history_text(items),
        reply_markup=_message_history_keyboard(deal_id, oldest_id, has_more),
    )
    await callback.answer()


@router.message(DealMessageState.content)
async def deal_message_content(message: Message, state: FSMContext) -> None:
    text = None
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
    if not text and not media_file_ids:
        await message.answer("Отправьте текст или медиа.")
        return
    data = await state.get_data()
    deal_id = data.get("deal_id")
    if deal_id is None:
        await message.answer("Deal is required.")
        await _clear_state_keep(state)
        return
    try:
        api_client.create_deal_message(
            int(deal_id),
            {
                "actor_tg_user_id": message.from_user.id,
                "text": text,
                "media_file_ids": media_file_ids,
            },
        )
        await message.answer("Сообщение отправлено.")
    except Exception as exc:
        await message.answer(f"Failed to send message: {exc}")
    await _clear_deal_draft(state, int(deal_id))
    await _clear_state_keep(state)
    await _send_deal_details(message, int(deal_id), state=state)


@router.callback_query(F.data.startswith(DEAL_CREATIVE_PREFIX))
async def deal_creative_start(callback: CallbackQuery, state: FSMContext) -> None:
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
    role = _resolve_deal_role(callback.from_user.id, deal)
    if role != ROLE_OWNER:
        if callback.message:
            await callback.message.answer("Only channel owner can create creative.")
        await callback.answer()
        return
    draft_available = await _get_deal_draft(state, deal_id) is not None
    if callback.message:
        await _set_active_deal(callback.message, state, deal, role, draft_available)
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
        await _clear_state_keep(state)
    await _send_deal_details(callback.message, deal_id, callback.from_user.id, state=state)
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_CREATIVE_CANCEL_PREFIX))
async def deal_creative_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    deal_id = int(callback.data.split(":", 1)[1])
    if await state.get_state():
        await _clear_state_keep(state)
    await _send_deal_details(callback.message, deal_id, callback.from_user.id, state=state)
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
        media_file_ids = [{"type": "photo", "file_id": message.photo[-1].file_id}]
    if message.document:
        media_file_ids = [{"type": "document", "file_id": message.document.file_id}]
    if not text and not media_file_ids:
        await message.answer("Send text or media.")
        return
    data = await state.get_data()
    payload = {
        "actor_tg_user_id": message.from_user.id,
        "text": text,
        "media_file_ids": media_file_ids,
    }
    try:
        api_client.create_creative(data["deal_id"], payload)
        await message.answer("Creative submitted for review")
    except Exception as exc:
        await message.answer(f"Failed to create creative: {exc}")
    await _clear_deal_draft(state, data["deal_id"])
    await _clear_state_keep(state)
    await _send_deal_details(message, data["deal_id"], state=state)


@router.callback_query(F.data.startswith(DEAL_CREATIVE_STATUS_PREFIX))
async def deal_creative_status_start(callback: CallbackQuery, state: FSMContext) -> None:
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
    role = _resolve_deal_role(callback.from_user.id, deal)
    if role != ROLE_ADVERTISER:
        if callback.message:
            await callback.message.answer("Only advertiser can review creative.")
        await callback.answer()
        return
    draft_available = await _get_deal_draft(state, deal_id) is not None
    if callback.message:
        await _set_active_deal(callback.message, state, deal, role, draft_available)
    if callback.message:
        try:
            creative = api_client.get_creative(deal_id, callback.from_user.id)
        except Exception as exc:
            await callback.message.answer(f"Failed to load creative: {exc}")
            await callback.answer()
            return
        await _send_creative_preview(callback.message, creative)
    await state.update_data(deal_id=deal_id)
    await state.set_state(CreativeStatusState.status)
    if callback.message:
        await callback.message.answer(
            "Select creative status.",
            reply_markup=_creative_status_keyboard(deal_id, ["DRAFT", "APPROVED"]),
        )
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_CREATIVE_STATUS_SET_PREFIX))
async def deal_creative_status_set(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    _, deal_id_value, status_value = callback.data.split(":", 2)
    deal_id = int(deal_id_value)
    status_value = status_value.upper()
    if status_value not in CREATIVE_STATUSES:
        await callback.message.answer("Unknown creative status.")
        await callback.answer()
        return
    try:
        deal = api_client.get_deal(deal_id)
    except Exception as exc:
        await callback.message.answer(f"Failed to load deal: {exc}")
        await callback.answer()
        return
    role = _resolve_deal_role(callback.from_user.id, deal)
    if role != ROLE_ADVERTISER:
        await callback.message.answer("Only advertiser can review creative.")
        await callback.answer()
        return
    if status_value == "DRAFT":
        await state.update_data(deal_id=deal_id, status=status_value)
        await state.set_state(CreativeStatusState.comment)
        await _prompt_creative_status_comment(callback.message, deal_id)
        await callback.answer()
        return
    if status_value == "APPROVED":
        if not deal.get("publish_at"):
            await state.update_data(deal_id=deal_id, status=status_value)
            await state.set_state(CreativeStatusState.publish_at)
            await _prompt_creative_status_publish_at(callback.message, deal_id)
            await callback.answer()
            return
    try:
        api_client.update_creative_status(
            deal_id,
            {"status": status_value, "actor_tg_user_id": callback.from_user.id},
        )
        await callback.message.answer("Creative status updated")
    except Exception as exc:
        await callback.message.answer(f"Failed to update creative status: {exc}")
    if await state.get_state():
        await _clear_state_keep(state)
    await _clear_deal_draft(state, deal_id)
    await _send_deal_details(callback.message, deal_id, callback.from_user.id, state=state)
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_CREATIVE_STATUS_BACK_PREFIX))
async def deal_creative_status_back(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    deal_id = int(callback.data.split(":", 1)[1])
    if await state.get_state():
        await _clear_state_keep(state)
    await _send_deal_details(callback.message, deal_id, callback.from_user.id, state=state)
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_CREATIVE_STATUS_CANCEL_PREFIX))
async def deal_creative_status_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    deal_id = int(callback.data.split(":", 1)[1])
    if await state.get_state():
        await _clear_state_keep(state)
    await _send_deal_details(callback.message, deal_id, callback.from_user.id, state=state)
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_CREATIVE_PREVIOUS_PREFIX))
async def deal_creative_previous(callback: CallbackQuery) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    _, deal_id_value, version_value = callback.data.split(":", 2)
    deal_id = int(deal_id_value)
    version = int(version_value)
    try:
        creative = api_client.get_creative(deal_id, callback.from_user.id, version=version)
    except Exception as exc:
        await callback.message.answer(f"Failed to load creative: {exc}")
        await callback.answer()
        return
    await callback.message.answer(f"Creative v{version}")
    await _send_creative_preview(callback.message, creative)
    await callback.answer()


@router.callback_query(F.data.startswith(DEAL_CREATIVE_VIEW_PREFIX))
async def deal_creative_view(callback: CallbackQuery) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    deal_id = int(callback.data.split(":", 1)[1])
    try:
        creative = api_client.get_creative(deal_id, callback.from_user.id)
    except Exception as exc:
        await callback.message.answer(f"Failed to load creative: {exc}")
        await callback.answer()
        return
    await _send_creative_preview(callback.message, creative)
    await callback.answer()


@router.message(CreativeStatusState.comment)
async def deal_creative_status_comment(message: Message, state: FSMContext) -> None:
    comment = (message.text or "").strip()
    if not comment:
        await message.answer("Comment is required.")
        return
    data = await state.get_data()
    deal_id = data["deal_id"]
    status_value = (data.get("status") or "DRAFT").upper()
    try:
        api_client.update_creative_status(
            deal_id,
            {"status": status_value, "actor_tg_user_id": message.from_user.id, "comment": comment},
        )
        await message.answer("Creative status updated")
    except Exception as exc:
        await message.answer(f"Failed to update creative status: {exc}")
    await _clear_deal_draft(state, deal_id)
    await _clear_state_keep(state)
    await _send_deal_details(message, deal_id, state=state)


@router.message(CreativeStatusState.publish_at)
async def deal_creative_status_publish_at(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    try:
        publish_at = _normalize_datetime(value)
    except ValueError:
        await message.answer("Invalid datetime. Use ISO format.")
        return
    if not publish_at:
        await message.answer("Publish_at is required.")
        return
    data = await state.get_data()
    deal_id = data["deal_id"]
    status_value = (data.get("status") or "APPROVED").upper()
    try:
        api_client.update_creative_status(
            deal_id,
            {
                "status": status_value,
                "actor_tg_user_id": message.from_user.id,
                "publish_at": publish_at,
            },
        )
        await message.answer("Creative status updated")
    except Exception as exc:
        await message.answer(f"Failed to update creative status: {exc}")
    await _clear_deal_draft(state, deal_id)
    await _clear_state_keep(state)
    await _send_deal_details(message, deal_id, state=state)


@router.message(CreativeStatusState.status)
async def deal_creative_status_value(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip().upper()
    if value not in CREATIVE_STATUSES:
        await message.answer("Unknown creative status.")
        return
    data = await state.get_data()
    deal_id = data["deal_id"]
    if value == "DRAFT":
        await state.update_data(status=value)
        await state.set_state(CreativeStatusState.comment)
        await _prompt_creative_status_comment(message, deal_id)
        return
    if value == "APPROVED":
        try:
            deal = api_client.get_deal(deal_id)
        except Exception as exc:
            await message.answer(f"Failed to load deal: {exc}")
            return
        if not deal.get("publish_at"):
            await state.update_data(status=value)
            await state.set_state(CreativeStatusState.publish_at)
            await _prompt_creative_status_publish_at(message, deal_id)
            return
    try:
        api_client.update_creative_status(
            deal_id,
            {"status": value, "actor_tg_user_id": message.from_user.id},
        )
        await message.answer("Creative status updated")
    except Exception as exc:
        await message.answer(f"Failed to update creative status: {exc}")
    await _clear_deal_draft(state, deal_id)
    await _clear_state_keep(state)
    await _send_deal_details(message, deal_id, state=state)


@router.message(Command("terms"))
@router.message(CommandTextFilter("terms"))
async def set_terms(message: Message, state: FSMContext) -> None:
    if await state.get_state():
        await _clear_state_keep(state)
    parts = (message.text or "").split()
    if len(parts) < 5:
        await message.answer("Usage: /terms DEAL_ID PRICE PUBLISH_AT ISO VERIFICATION_MINUTES [FORMAT]")
        return
    try:
        deal_id = int(parts[1])
        price = float(parts[2])
        publish_at = parts[3]
        verification_window = int(parts[4])
    except ValueError:
        await message.answer("Usage: /terms DEAL_ID PRICE PUBLISH_AT ISO VERIFICATION_MINUTES [FORMAT]")
        return
    format_value = parts[5] if len(parts) > 5 else "post"
    payload = {
        "actor_tg_user_id": message.from_user.id,
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
    await _clear_deal_draft(state, deal_id)
    await _send_deal_details(message, deal_id, state=state, set_active=True)


@router.message(Command("status"))
@router.message(CommandTextFilter("status"))
async def set_status(message: Message, state: FSMContext) -> None:
    if await state.get_state():
        await _clear_state_keep(state)
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer("Usage: /status DEAL_ID STATUS")
        return
    try:
        deal_id = int(parts[1])
    except ValueError:
        await message.answer("Usage: /status DEAL_ID STATUS")
        return
    status_value = parts[2]
    try:
        api_client.update_status(
            deal_id,
            {"status": status_value, "actor_tg_user_id": message.from_user.id},
        )
        await message.answer("Status updated")
    except Exception as exc:
        await message.answer(f"Failed to update status: {exc}")
    await _clear_deal_draft(state, deal_id)
    await _send_deal_details(message, deal_id, state=state, set_active=True)


@router.message(Command("creative"))
@router.message(CommandTextFilter("creative"))
async def create_creative(message: Message, state: FSMContext) -> None:
    if await state.get_state():
        await _clear_state_keep(state)
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2:
        await message.answer("Usage: /creative DEAL_ID [TEXT]")
        return
    try:
        deal_id = int(parts[1])
    except ValueError:
        await message.answer("Usage: /creative DEAL_ID [TEXT]")
        return
    text = parts[2] if len(parts) > 2 else None
    media_file_ids = None
    if message.photo:
        media_file_ids = [{"type": "photo", "file_id": message.photo[-1].file_id}]
    if message.document:
        media_file_ids = [{"type": "document", "file_id": message.document.file_id}]
    payload = {
        "actor_tg_user_id": message.from_user.id,
        "text": text,
        "media_file_ids": media_file_ids,
    }
    try:
        api_client.create_creative(deal_id, payload)
        await message.answer("Creative submitted for review")
    except Exception as exc:
        await message.answer(f"Failed to create creative: {exc}")
    await _clear_deal_draft(state, deal_id)
    await _send_deal_details(message, deal_id, state=state, set_active=True)


@router.message(Command("creative_status"))
@router.message(CommandTextFilter("creative_status"))
async def creative_status(message: Message, state: FSMContext) -> None:
    if await state.get_state():
        await _clear_state_keep(state)
    parts = (message.text or "").split(maxsplit=3)
    if len(parts) < 3:
        await message.answer("Usage: /creative_status DEAL_ID STATUS")
        return
    try:
        deal_id = int(parts[1])
    except ValueError:
        await message.answer("Usage: /creative_status DEAL_ID STATUS")
        return
    status_value = parts[2].upper()
    extra = parts[3].strip() if len(parts) > 3 else ""
    payload = {"status": status_value, "actor_tg_user_id": message.from_user.id}
    if status_value == "DRAFT":
        if not extra:
            await message.answer("Comment required. Usage: /creative_status DEAL_ID DRAFT COMMENT")
            return
        payload["comment"] = extra
    if status_value == "APPROVED":
        publish_at = None
        try:
            deal = api_client.get_deal(deal_id)
            publish_at = deal.get("publish_at")
        except Exception as exc:
            await message.answer(f"Failed to load deal: {exc}")
            return
        if not publish_at:
            if not extra:
                await message.answer("publish_at required. Usage: /creative_status DEAL_ID APPROVED PUBLISH_AT")
                return
            try:
                publish_at = _normalize_datetime(extra)
            except ValueError:
                await message.answer("Invalid datetime. Use ISO format.")
                return
            if not publish_at:
                await message.answer("Publish_at is required.")
                return
            payload["publish_at"] = publish_at
    try:
        api_client.update_creative_status(
            deal_id,
            payload,
        )
        await message.answer("Creative status updated")
    except Exception as exc:
        await message.answer(f"Failed to update creative status: {exc}")
    await _clear_deal_draft(state, deal_id)
    await _send_deal_details(message, deal_id, state=state, set_active=True)


@router.message(F.text)
async def fallback_commands(message: Message, state: FSMContext) -> None:
    command = _extract_command(message.text)
    if command == "deal":
        await deal_info(message, state)
        return
    if command == "terms":
        await set_terms(message, state)
        return
    if command == "status":
        await set_status(message, state)
        return
    if command == "creative":
        await create_creative(message, state)
        return
    if command == "creative_status":
        await creative_status(message, state)
