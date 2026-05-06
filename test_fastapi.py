import asyncio, sys, os
from dotenv import load_dotenv
load_dotenv("backend/.env")
sys.path.append(os.getcwd()+"/backend")

from fastapi import Request
from backend.routers.admin import test_wecom_notify

class MockRequest:
    headers = {"X-Admin-Secret": os.getenv("ADMIN_SECRET")}
    def __init__(self):
        pass

async def main():
    try:
        res = test_wecom_notify(MockRequest(), "qC34flxZ7fRC5ADywofM9x9fj3g2", "2026-04-19")
        print("RESULT:")
        import pprint
        pprint.pprint(res)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(main())
