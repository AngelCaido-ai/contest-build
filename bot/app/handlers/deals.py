from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.app.services import api_client

router = Router()


@router.message(Command("deal"))
async def deal_info(message: Message) -> None:
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /deal DEAL_ID")
        return
    deal_id = int(parts[1])
    deal = api_client.get_deal(deal_id)
    await message.answer(f"Deal {deal_id} status: {deal.get('status')}")


@router.message(Command("terms"))
async def set_terms(message: Message) -> None:
    parts = message.text.split()
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
    api_client.update_terms(deal_id, payload)
    await message.answer("Terms updated")


@router.message(Command("status"))
async def set_status(message: Message) -> None:
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Usage: /status DEAL_ID STATUS")
        return
    deal_id = int(parts[1])
    status_value = parts[2]
    api_client.update_status(deal_id, status_value)
    await message.answer("Status updated")


@router.message(Command("creative"))
async def create_creative(message: Message) -> None:
    parts = message.text.split(maxsplit=2)
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
    api_client.create_creative(deal_id, payload)
    await message.answer("Creative drafted")


@router.message(Command("creative_status"))
async def creative_status(message: Message) -> None:
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Usage: /creative_status DEAL_ID STATUS")
        return
    deal_id = int(parts[1])
    status_value = parts[2]
    api_client.update_creative_status(deal_id, status_value)
    await message.answer("Creative status updated")
