import asyncio

from aiogram import Bot, Dispatcher

from bot.app.config import settings
from bot.app.handlers import channel_posts, deals, onboarding, start


async def main() -> None:
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    dp.include_router(start.router)
    dp.include_router(onboarding.router)
    dp.include_router(deals.router)
    dp.include_router(channel_posts.router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
