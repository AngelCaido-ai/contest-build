from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("start"))
async def start_handler(message: Message) -> None:
    await message.answer("Bot is running. Use /add_channel, /deal, /terms, /status, /creative")
