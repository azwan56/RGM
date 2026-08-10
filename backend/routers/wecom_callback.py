import asyncio
import os
import xml.etree.ElementTree as ET
from fastapi import APIRouter, Request, Query, BackgroundTasks, HTTPException
from fastapi.responses import PlainTextResponse

from utils.wecom_crypto import WXBizMsgCrypt

router = APIRouter(redirect_slashes=False)

def get_crypto() -> WXBizMsgCrypt:
    token = os.getenv("WECOM_CALLBACK_TOKEN", "")
    encoding_aes_key = os.getenv("WECOM_CALLBACK_AES_KEY", "")
    corp_id = os.getenv("WECOM_CORP_ID", "")
    
    if not token or not encoding_aes_key or not corp_id:
        raise ValueError("WeCom callback configuration is missing")
        
    return WXBizMsgCrypt(token, encoding_aes_key, corp_id)

@router.get("/")
@router.get("")
async def verify_url(
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...)
):
    """WeCom URL verification endpoint."""
    try:
        crypto = get_crypto()
        decrypted_echostr = crypto.verify_url(msg_signature, timestamp, nonce, echostr)
        # Must return the decrypted string directly as plain text
        return PlainTextResponse(content=decrypted_echostr)
    except ValueError as ve:
        print(f"[wecom_callback] Config check: TOKEN set={bool(os.getenv('WECOM_CALLBACK_TOKEN'))}, AES set={bool(os.getenv('WECOM_CALLBACK_AES_KEY'))}, CORP_ID set={bool(os.getenv('WECOM_CORP_ID'))}")
        print(f"[wecom_callback] Verification failed: {ve}")
        raise HTTPException(status_code=400, detail=f"Verification failed: {ve}")
    except Exception as e:
        print(f"[wecom_callback] Unexpected error: {type(e).__name__}: {e}")
        raise HTTPException(status_code=400, detail=f"Verification failed: {e}")

@router.post("/")
@router.post("")
async def receive_message(
    request: Request,
    background_tasks: BackgroundTasks,
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...)
):
    """Receive pushed messages from WeCom (supports both XML and JSON callbacks)."""
    print(f"[wecom_callback] ▶ POST received, sig={msg_signature[:16]}...")
    try:
        body = await request.body()
        print(f"[wecom_callback]   body length={len(body)}, raw snippet={body[:150]!r}")
        
        encrypt = None
        import json
        
        # 1. Try JSON body parsing (Intelligent Robot callbacks)
        try:
            json_body = json.loads(body)
            if isinstance(json_body, dict):
                encrypt = json_body.get("encrypt") or json_body.get("Encrypt")
        except Exception:
            pass

        # 2. Try XML body parsing (Self-built App callbacks)
        if not encrypt:
            try:
                xml_tree = ET.fromstring(body)
                encrypt_node = xml_tree.find("Encrypt")
                if encrypt_node is not None:
                    encrypt = encrypt_node.text
            except Exception as xe:
                print(f"[wecom_callback] XML parse failed: {xe}")

        if not encrypt:
            print("[wecom_callback] ✗ Could not extract Encrypt field from request body")
            return PlainTextResponse(content="success")

        crypto = get_crypto()
        decrypted_raw = crypto.decrypt_msg(msg_signature, timestamp, nonce, encrypt)
        print(f"[wecom_callback]   decrypted_raw snippet={decrypted_raw[:150]!r}")

        msg_data = {}
        # 3. Try parsing decrypted content as JSON
        try:
            msg_data = json.loads(decrypted_raw)
        except Exception:
            # 4. Fallback: Parse decrypted content as XML
            try:
                msg_tree = ET.fromstring(decrypted_raw)
                for child in msg_tree:
                    if len(child) == 0:
                        msg_data[child.tag] = child.text
                    else:
                        msg_data[child.tag] = child.text
                        for sub in child:
                            msg_data[sub.tag] = sub.text
            except Exception as xe2:
                print(f"[wecom_callback] Decrypted XML parse failed: {xe2}")

        # Normalize JSON keys to match expected WeCom keys if needed
        if "msgtype" in msg_data and "MsgType" not in msg_data:
            msg_data["MsgType"] = msg_data["msgtype"]
        if "from" in msg_data and "FromUserName" not in msg_data:
            msg_data["FromUserName"] = msg_data["from"].get("userid", "") if isinstance(msg_data["from"], dict) else str(msg_data["from"])
        if "text" in msg_data and isinstance(msg_data["text"], dict) and "Content" not in msg_data:
            msg_data["Content"] = msg_data["text"].get("content", "")
        if "chatid" in msg_data and "ChatId" not in msg_data:
            msg_data["ChatId"] = msg_data["chatid"]

        print(f"[wecom_callback]   decrypted msg_data keys={list(msg_data.keys())}, MsgType={msg_data.get('MsgType')}, Content={str(msg_data.get('Content', ''))[:60]!r}")

        # WeCom expects an immediate acknowledgment ("success")
        from utils.wecom_bot import handle_wecom_message
        loop = asyncio.get_event_loop()
        background_tasks.add_task(handle_wecom_message, msg_data, loop=loop)

        return PlainTextResponse(content="success")

    except Exception as e:
        print(f"[wecom_callback] ✗ Message processing failed: {e}")
        import traceback
        traceback.print_exc()
        return PlainTextResponse(content="success")
