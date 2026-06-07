import inspect
from wecom_aibot_sdk import WSClient
client = WSClient({"bot_id": "a", "secret": "b"})
m = getattr(client, 'download_file')
print("is_coroutine:", inspect.iscoroutinefunction(m))
print("signature:", inspect.signature(m))
