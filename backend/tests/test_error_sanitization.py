from utils.discord import clean_err

def test_clean_err_discord_webhook():
    # Test discord webhook url in error message
    url = "https://discord.com/api/webhooks/123456789/discordkey"
    raw_error = Exception(f"Connection failed to {url}")
    sanitized = clean_err(raw_error)
    assert url not in sanitized
    assert "MASKED_ID" in sanitized
    assert "MASKED_TOKEN" in sanitized

def test_clean_err_wecom_webhook():
    # Test WeCom webhook url in error message
    url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=wecomkey"
    raw_error = Exception(f"Failed to post to {url}")
    sanitized = clean_err(raw_error)
    assert url not in sanitized
    assert "MASKED_KEY" in sanitized

def test_clean_err_wecom_access_token():
    # Test access token masking
    raw_error = Exception("Failed with access_token=wecomtoken")
    sanitized = clean_err(raw_error)
    assert "wecomtoken" not in sanitized
    assert "access_token=MASKED_TOKEN" in sanitized

def test_clean_err_wecom_corp_secret():
    # Test WeChat corpsecret url parameter masking
    raw_error = Exception("URL error: corpsecret=corpsecret")
    sanitized = clean_err(raw_error)
    assert "corpsecret=MASKED_SECRET" in sanitized

def test_clean_err_strava_client_secret():
    # Test Strava client secret parameter masking
    raw_error = Exception("Request failed: client_secret=stravasecret")
    sanitized = clean_err(raw_error)
    assert "client_secret=MASKED_SECRET" in sanitized
