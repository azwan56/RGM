import os
import sys
import pytest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Mock the entire firebase_config before import to prevent actual firebase connections
sys.modules['firebase_config'] = mock.MagicMock()

from utils.wecom_bot import (
    _download_wecom_media,
    _generate_reply,
    handle_wecom_message
)

@mock.patch("utils.wecom_bot._get_wecom_access_token")
@mock.patch("requests.get")
def test_download_wecom_media(mock_get, mock_token):
    mock_token.return_value = "fake_access_token"
    
    # 1. Test success case (returns image/jpeg content)
    mock_resp = mock.MagicMock()
    mock_resp.ok = True
    mock_resp.headers = {"Content-Type": "image/jpeg"}
    mock_resp.content = b"fake_jpeg_bytes"
    mock_get.return_value = mock_resp
    
    res = _download_wecom_media("fake_media_id")
    assert res is not None
    assert res["mimeType"] == "image/jpeg"
    assert "data" in res
    
    # 2. Test non-image content type
    mock_resp.headers = {"Content-Type": "text/plain"}
    res = _download_wecom_media("fake_media_id")
    assert res is None

@pytest.mark.anyio
@mock.patch("utils.wecom_bot._fetch_latest_training_plan", return_value={})
@mock.patch("utils.wecom_bot._fetch_latest_coach_analysis", return_value={})
@mock.patch("utils.wecom_bot._gemini_generate")
@mock.patch("utils.wecom_bot._resolve_user_by_wecom_id")
@mock.patch("utils.wecom_bot._save_chat_message")
async def test_generate_reply_with_image(mock_save, mock_resolve, mock_gemini, mock_analysis, mock_plan):
    mock_resolve.return_value = ("test_uid", {"display_name": "Test User"})
    mock_gemini.return_value = {"text": "Bonnie's funny response"}
    
    reply_received = []
    async def mock_reply_func(msg):
        reply_received.append(msg)
        
    inline_data = {"mimeType": "image/jpeg", "data": "base64_data"}
    
    await _generate_reply(
        content="请帮我看看这张图片",
        wecom_user_id="wecom_123",
        chatid="chat_123",
        reply_func=mock_reply_func,
        inline_data=inline_data
    )
    
    assert len(reply_received) == 1
    assert reply_received[0] == "Bonnie's funny response"
    
    # Verify that gemini was called with content_obj containing inlineData
    called_kwargs = mock_gemini.call_args[1]
    contents_obj = called_kwargs.get("contents_obj")
    assert contents_obj is not None
    
    # Verify that the last message has inlineData
    last_msg = contents_obj[-1]
    assert last_msg["role"] == "user"
    assert len(last_msg["parts"]) == 2
    assert "inlineData" in last_msg["parts"][0]
    assert last_msg["parts"][0]["inlineData"] == inline_data
    assert "text" in last_msg["parts"][1]
    assert "用户提供了一张图片/文件" in last_msg["parts"][1]["text"]

@mock.patch("utils.wecom_bot._generate_reply")
@mock.patch("utils.wecom_bot._download_wecom_media")
@mock.patch("utils.wecom_bot.send_bonnie_message")
def test_handle_wecom_message_types(mock_send, mock_download, mock_generate):
    mock_download.return_value = {"mimeType": "image/jpeg", "data": "base64"}
    
    # 1. Test image msgtype
    msg_image = {
        "MsgType": "image",
        "MediaId": "media_id_123",
        "FromUserName": "user_abc"
    }
    handle_wecom_message(msg_image)
    mock_download.assert_called_with("media_id_123")
    mock_generate.assert_called()
    
    # 2. Test unsupported file msgtype
    msg_file_unsupported = {
        "MsgType": "file",
        "Title": "workout_plan.pdf",
        "MediaId": "media_id_456",
        "FromUserName": "user_abc"
    }
    mock_generate.reset_mock()
    handle_wecom_message(msg_file_unsupported)
    mock_generate.assert_not_called()
    mock_send.assert_called_with("user_abc", mock.ANY)
    
    # 3. Test supported file msgtype (e.g. .png)
    msg_file_supported = {
        "MsgType": "file",
        "Title": "screenshot.png",
        "MediaId": "media_id_789",
        "FromUserName": "user_abc"
    }
    mock_send.reset_mock()
    handle_wecom_message(msg_file_supported)
    mock_generate.assert_called()
    mock_send.assert_not_called()
