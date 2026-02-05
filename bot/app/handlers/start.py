from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("start"))
async def start_handler(message: Message) -> None:
    await message.answer(
        "Bot is running. Use /menu, /add_channel, /channels, /listings, /requests, /create_listing, "
        "/create_request, /respond_request, /deals, /deal, /terms, /status, /creative, /creative_status, /wallet, /cancel"
    )
