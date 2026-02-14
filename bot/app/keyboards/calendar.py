import calendar as _calendar
import logging
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

logger = logging.getLogger(__name__)

MSK = timezone(timedelta(hours=3))

DTP_NAV = "dtp:nav:"
DTP_DAY = "dtp:day:"
DTP_HOUR = "dtp:hr:"
DTP_MIN = "dtp:mn:"
DTP_IGNORE = "dtp:ign"
DTP_SKIP = "dtp:skip"

CAL_CONTEXT_KEY = "cal_context"
CAL_DEAL_ID_KEY = "cal_deal_id"

MONTH_NAMES = [
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

WEEKDAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


def _ign_btn(text: str = " ") -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=DTP_IGNORE)


def build_calendar_keyboard(
    year: int,
    month: int,
    skip_allowed: bool = False,
) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()

    prev_m, prev_y = (month - 1, year) if month > 1 else (12, year - 1)
    next_m, next_y = (month + 1, year) if month < 12 else (1, year + 1)

    builder.row(
        InlineKeyboardButton(text="◀", callback_data=f"{DTP_NAV}{prev_y}-{prev_m:02d}"),
        _ign_btn(f"{MONTH_NAMES[month]} {year}"),
        InlineKeyboardButton(text="▶", callback_data=f"{DTP_NAV}{next_y}-{next_m:02d}"),
    )

    builder.row(*[_ign_btn(d) for d in WEEKDAYS])

    today = datetime.now(MSK).date()
    weeks = _calendar.monthcalendar(year, month)

    for week in weeks:
        row: list[InlineKeyboardButton] = []
        for day in week:
            if day == 0:
                row.append(_ign_btn())
            else:
                d = datetime(year, month, day).date()
                if d < today:
                    row.append(_ign_btn("·"))
                else:
                    label = f"[{day}]" if d == today else str(day)
                    row.append(
                        InlineKeyboardButton(
                            text=label,
                            callback_data=f"{DTP_DAY}{year}-{month:02d}-{day:02d}",
                        )
                    )
        builder.row(*row)

    if skip_allowed:
        builder.row(InlineKeyboardButton(text="Skip", callback_data=DTP_SKIP))

    return builder


def build_hour_keyboard(date_str: str) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.row(_ign_btn(f"📅 {_format_date_label(date_str)} — hour"))

    for start in range(0, 24, 6):
        row = []
        for h in range(start, start + 6):
            row.append(
                InlineKeyboardButton(
                    text=f"{h:02d}",
                    callback_data=f"{DTP_HOUR}{date_str}:{h:02d}",
                )
            )
        builder.row(*row)

    parts = date_str.rsplit("-", 1)
    ym = f"{parts[0]}" if len(parts) == 2 else date_str[:7]
    builder.row(InlineKeyboardButton(text="◀ Back", callback_data=f"{DTP_NAV}{ym}"))
    return builder


def build_minute_keyboard(date_str: str, hour: str) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.row(_ign_btn(f"📅 {_format_date_label(date_str)} {hour}:__ — minutes"))

    for start in range(0, 60, 30):
        row = []
        for m in range(start, start + 30, 5):
            row.append(
                InlineKeyboardButton(
                    text=f":{m:02d}",
                    callback_data=f"{DTP_MIN}{date_str}:{hour}:{m:02d}",
                )
            )
        builder.row(*row)

    builder.row(InlineKeyboardButton(text="◀ Back", callback_data=f"{DTP_DAY}{date_str}"))
    return builder


def _format_date_label(date_str: str) -> str:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.strftime("%d.%m.%Y")
    except ValueError:
        return date_str


router = Router()


@router.callback_query(F.data == DTP_IGNORE)
async def _on_ignore(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith(DTP_NAV))
async def _on_navigate(callback: CallbackQuery, state: FSMContext) -> None:
    raw = callback.data[len(DTP_NAV):]
    try:
        parts = raw.split("-")
        year, month = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        await callback.answer("Navigation error")
        return

    data = await state.get_data()
    skip_allowed = data.get("cal_skip_allowed", False)

    kb = build_calendar_keyboard(year, month, skip_allowed=skip_allowed)
    if callback.message:
        try:
            await callback.message.edit_text(
                "Select publish date:",
                reply_markup=kb.as_markup(),
            )
        except Exception:
            pass
    await callback.answer()


@router.callback_query(F.data.startswith(DTP_DAY))
async def _on_day(callback: CallbackQuery) -> None:
    date_str = callback.data[len(DTP_DAY):]
    kb = build_hour_keyboard(date_str)
    if callback.message:
        try:
            await callback.message.edit_text(
                "Select hour:",
                reply_markup=kb.as_markup(),
            )
        except Exception:
            pass
    await callback.answer()


@router.callback_query(F.data.startswith(DTP_HOUR))
async def _on_hour(callback: CallbackQuery) -> None:
    raw = callback.data[len(DTP_HOUR):]
    parts = raw.rsplit(":", 1)
    if len(parts) != 2:
        await callback.answer("Error")
        return
    date_str, hour = parts[0], parts[1]
    kb = build_minute_keyboard(date_str, hour)
    if callback.message:
        try:
            await callback.message.edit_text(
                "Select minutes:",
                reply_markup=kb.as_markup(),
            )
        except Exception:
            pass
    await callback.answer()


@router.callback_query(F.data.startswith(DTP_MIN))
async def _on_minute(callback: CallbackQuery, state: FSMContext) -> None:
    raw = callback.data[len(DTP_MIN):]
    parts = raw.rsplit(":", 2)
    if len(parts) != 3:
        await callback.answer("Error")
        return
    date_str, hour, minute = parts[0], parts[1], parts[2]
    iso_str = f"{date_str}T{hour}:{minute}:00+03:00"
    display = f"{_format_date_label(date_str)} {hour}:{minute}"

    if callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass

    await _dispatch_result(callback, state, iso_str, display)


@router.callback_query(F.data == DTP_SKIP)
async def _on_skip(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass

    await _dispatch_result(callback, state, None, None)


async def _dispatch_result(
    callback: CallbackQuery,
    state: FSMContext,
    iso_str: str | None,
    display: str | None,
) -> None:
    data = await state.get_data()
    ctx = data.get(CAL_CONTEXT_KEY, "")
    deal_id = data.get(CAL_DEAL_ID_KEY) or data.get("deal_id")
    msg = callback.message

    if ctx == "terms":
        from bot.app.handlers.deals import (
            DealTermsState,
            _prompt_terms_verification_window,
        )

        await state.update_data(publish_at=iso_str)
        await state.set_state(DealTermsState.verification_window)
        if msg:
            if display:
                await msg.answer(f"📅 Publish date: {display}")
            await _prompt_terms_verification_window(msg, deal_id)

    elif ctx == "publish_at":
        from bot.app.handlers.deals import _clear_state_keep, _send_deal_details
        from bot.app.services import api_client

        payload = {"actor_tg_user_id": callback.from_user.id, "publish_at": iso_str}
        try:
            api_client.update_publish_at(deal_id, payload)
            if msg:
                await msg.answer(f"📅 Publish time updated: {display}")
        except Exception as exc:
            if msg:
                await msg.answer(f"Error: {exc}")
        await _clear_state_keep(state)
        if msg:
            await _send_deal_details(msg, deal_id, state=state)

    elif ctx == "creative_status":
        from bot.app.handlers.deals import (
            _clear_deal_draft,
            _clear_state_keep,
            _send_deal_details,
        )
        from bot.app.services import api_client

        status_value = (data.get("status") or "APPROVED").upper()
        try:
            api_client.update_creative_status(
                deal_id,
                {
                    "status": status_value,
                    "actor_tg_user_id": callback.from_user.id,
                    "publish_at": iso_str,
                },
            )
            if msg:
                await msg.answer(f"📅 Creative approved, date: {display}")
        except Exception as exc:
            if msg:
                await msg.answer(f"Error: {exc}")
        await _clear_deal_draft(state, deal_id)
        await _clear_state_keep(state)
        if msg:
            await _send_deal_details(msg, deal_id, state=state)

    elif ctx == "listing_respond":
        from bot.app.handlers.marketplace import (
            ListingRespondState,
            _prompt_listing_respond_creative,
        )

        await state.update_data(publish_at=iso_str)
        await state.set_state(ListingRespondState.creative)
        if msg:
            if display:
                await msg.answer(f"📅 Publish date: {display}")
            elif iso_str is None:
                await msg.answer("Publish date skipped.")
            await _prompt_listing_respond_creative(msg)

    await callback.answer()
