import os
import xml.etree.ElementTree as ET
from fastapi import APIRouter, Request, Query, BackgroundTasks, HTTPException
from fastapi.responses import PlainTextResponse

from utils.wecom_crypto import WXBizMsgCrypt

router = APIRouter()

def get_crypto() -> WXBizMsgCrypt:
    token = os.getenv("WECOM_CALLBACK_TOKEN", "")
    encoding_aes_key = os.getenv("WECOM_CALLBACK_AES_KEY", "")
    corp_id = os.getenv("WECOM_CORP_ID", "")
    
    if not token or not encoding_aes_key or not corp_id:
        raise ValueError("WeCom callback configuration is missing")
        
    return WXBizMsgCrypt(token, encoding_aes_key, corp_id)

@router.get("/")
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
    except Exception as e:
        print(f"[wecom_callback] Verification failed: {e}")
        raise HTTPException(status_code=400, detail="Verification failed")

@router.post("/")
async def receive_message(
    request: Request,
    background_tasks: BackgroundTasks,
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...)
):
    """Receive pushed messages from WeCom."""
    print(f"[wecom_callback] ▶ POST received, sig={msg_signature[:16]}...")
    try:
        body = await request.body()
        print(f"[wecom_callback]   body length={len(body)}")
        xml_tree = ET.fromstring(body)
        encrypt = xml_tree.find("Encrypt").text
        
        crypto = get_crypto()
        decrypted_xml = crypto.decrypt_msg(msg_signature, timestamp, nonce, encrypt)
        
        msg_tree = ET.fromstring(decrypted_xml)
        msg_data = {child.tag: child.text for child in msg_tree}
        print(f"[wecom_callback]   decrypted msg_data keys={list(msg_data.keys())}, MsgType={msg_data.get('MsgType')}, Content={str(msg_data.get('Content', ''))[:60]!r}")
        
        # WeCom expects an immediate acknowledgment (empty string or "success")
        # Process the actual message in the background
        from utils.wecom_bot import handle_wecom_message
        background_tasks.add_task(handle_wecom_message, msg_data)
        
        return PlainTextResponse(content="success")
        
    except Exception as e:
        print(f"[wecom_callback] ✗ Message processing failed: {e}")
        import traceback
        traceback.print_exc()
        return PlainTextResponse(content="success") # still return success to prevent retries
