import asyncio
import logging

from telethon import TelegramClient, events
from telethon.sessions import StringSession

from watcher.app.config import settings
from watcher.app.handlers import close_client, init_client, on_message_deleted, on_message_edited

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("Watcher starting (Telethon userbot)")
    logger.info("API base URL: %s", settings.api_base_url)

    client = TelegramClient(
        StringSession(settings.telethon_session),
        settings.telethon_api_id,
        settings.telethon_api_hash,
    )

    await client.start()
    me = await client.get_me()
    logger.info("Watcher connected as: %s (id=%s)", me.username or me.first_name, me.id)

    init_client()
    logger.info("Watcher httpx AsyncClient initialized")

    client.add_event_handler(on_message_edited, events.MessageEdited(chats=None))
    client.add_event_handler(on_message_deleted, events.MessageDeleted(chats=None))
    logger.info("Event handlers registered: MessageEdited, MessageDeleted")

    try:
        logger.info("Watcher running, listening for events...")
        await client.run_until_disconnected()
    finally:
        await close_client()
        logger.info("Watcher stopped")


if __name__ == "__main__":
    asyncio.run(main())
