import logging
import re

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.app.services import api_client

logger = logging.getLogger(__name__)
router = Router()

DEEP_LINK_DEAL_RE = re.compile(r"^deal_(\d+)$")


@router.message(Command("start"))
async def start_handler(
    message: Message,
    command: CommandObject,
    state: FSMContext,
) -> None:
    try:
        await api_client.upsert_user(message.from_user.id, message.from_user.username)
        logger.info("start: upsert user tg_user_id=%s", message.from_user.id)
    except Exception:
        logger.exception("start: upsert_user failed tg_user_id=%s", message.from_user.id)

    if command.args:
        match = DEEP_LINK_DEAL_RE.match(command.args)
        if match:
            from bot.app.handlers.deals import (
                DEAL_FLOW_STATES,
                _clear_state_keep,
                _maybe_prompt_deal_switch,
                _send_deal_details,
            )

            deal_id = int(match.group(1))
            if await _maybe_prompt_deal_switch(message, state, deal_id):
                return
            current_state = await state.get_state()
            if current_state and current_state not in DEAL_FLOW_STATES:
                await _clear_state_keep(state)
            await _send_deal_details(message, deal_id, state=state, set_active=True)
            return

    await message.answer(
        "Bot is running. Use /menu, /add_channel, /channels, /assigned_channels, /listings, /requests, "
        "/create_listing, /create_request, /respond_request, /deals, /deal, /terms, /status, /creative, "
        "/creative_status, /add_manager, /list_managers, /remove_manager, /test_deal, /cancel"
    )


@router.message(Command("test_deal"))
async def test_deal_handler(message: Message) -> None:
    try:
        await api_client.upsert_user(message.from_user.id, message.from_user.username)
        result = await api_client.create_test_deal(message.from_user.id)
        deal_id = result.get("deal_id")
        publish_at = result.get("publish_at")
        window = result.get("verification_window")
        await message.answer(
            f"Test deal created!\n"
            f"Deal #{deal_id}\n"
            f"Status: SCHEDULED\n"
            f"Creative: \"testtest\"\n"
            f"Publish at: {publish_at}\n"
            f"Verification window: {window} min\n\n"
            f"Post will be published in ~2 min, then you have {window} min to test tamper/delete detection."
        )
    except Exception as exc:
        logger.exception("test_deal: error tg_user_id=%s", message.from_user.id)
        await message.answer(f"Failed to create test deal: {exc}")
