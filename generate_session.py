from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = 25742504
api_hash = "4c1bd1d1bb626e40e0b4cf40c858849d"

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("\n✅ TELETHON_SESSION:")
    print(client.session.save())
