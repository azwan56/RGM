import io
import json
import struct
import sys
import types
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import routers.assistant as assistant_mod
import utils.local_store as ls_mod
from config import settings
from main import app
from utils.local_store import LocalStore, init_db


def _make_minimal_wav_bytes(duration_ms: int = 200, sample_rate: int = 16000) -> bytes:
    num_samples = max(1, int(sample_rate * duration_ms / 1000))
    data_size = num_samples * 2
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        sample_rate,
        sample_rate * 2,
        2,
        16,
        b"data",
        data_size,
    )
    return header + (b"\x00\x00" * num_samples)


@pytest.fixture()
def isolated_env(tmp_path, monkeypatch):
    db_file = str(tmp_path / "assistant_test.db")
    monkeypatch.setattr(ls_mod, "DB_PATH", db_file)
    LocalStore.invalidate_uid_cache()
    init_db()
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(
    "query,roles,expected_id",
    [
        ("我想绑定佳明运动手表", {"logged_in": True}, "bind-garmin"),
        ("高驰手表怎么连", {"logged_in": True}, "bind-coros"),
        ("提示我还有13天要补齐复旦戈实名资料", {"logged_in": True}, "org-required-fields"),
        ("帮我制定一套马拉松训练课表", {"logged_in": True}, "generate-plan"),
        ("想找附近配速差不多的跑步搭子", {"logged_in": True}, "discover-buddies"),
        ("我是教练，想导入Excel周训练课表分AB组", {"logged_in": True, "is_coach_or_owner": True}, "import-schedule"),
        ("打开教练5秒批阅连续点评队员", {"logged_in": True, "is_coach_or_owner": True}, "batch-critique"),
        ("导出本周跑团周报和微信群接龙", {"logged_in": True, "is_coach_or_owner": True}, "club-report"),
        ("管理员审核大群实名花名册和导出保险名单", {"logged_in": True, "has_managed_org": True}, "org-roster-audit"),
    ],
)
def test_navigate_deterministic_colloquial_queries(isolated_env, monkeypatch, query, roles, expected_id):
    monkeypatch.setattr(assistant_mod.llm_client, "_get_client", lambda: None)

    res = isolated_env.post(
        "/api/assistant/navigate",
        json={"query": query, "current_path": "/dashboard", "user_roles": roles},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["engine"] == "deterministic"
    assert data["primary_id"] == expected_id
    assert data["permission_ok"] is True
    assert data["auto_navigate"] is True


def test_navigate_llm_json_and_fenced_markdown(isolated_env, monkeypatch):
    monkeypatch.setattr(assistant_mod.llm_client, "_get_client", lambda: object())

    def fake_chat(messages, temperature=0.1, max_tokens=360, **kwargs):
        return (
            "```json\n"
            + json.dumps(
                {
                    "primary_id": "privacy-settings",
                    "alternative_ids": ["data-purge"],
                    "reply": "已为您直达 4 级隐私开关，可隐藏 GPS 轨迹。",
                    "confidence": 0.96,
                },
                ensure_ascii=False,
            )
            + "\n```"
        )

    monkeypatch.setattr(assistant_mod.llm_client, "chat_completion", fake_chat)

    res = isolated_env.post(
        "/api/assistant/navigate",
        json={
            "query": "不想让别人看到我跑步路线",
            "current_path": "/dashboard",
            "user_roles": {"logged_in": True},
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["engine"] == "llm"
    assert data["primary_id"] == "privacy-settings"
    assert data["alternative_ids"] == ["data-purge"]
    assert data["confidence"] == 0.96
    assert data["auto_navigate"] is True


def test_navigate_llm_plain_json_backfills_alternatives(isolated_env, monkeypatch):
    monkeypatch.setattr(assistant_mod.llm_client, "_get_client", lambda: object())

    def fake_chat_plain(messages, **kwargs):
        return json.dumps(
            {
                "primary_id": "taper-simulation",
                "alternative_ids": ["invalid-id", "taper-simulation"],
                "reply": "正在前往 Taper 赛前减量推演模拟器。",
                "confidence": 0.91,
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(assistant_mod.llm_client, "chat_completion", fake_chat_plain)

    res = isolated_env.post(
        "/api/assistant/navigate",
        json={"query": "赛前最后一周怎么减量", "user_roles": {"logged_in": True}},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["engine"] == "llm"
    assert data["primary_id"] == "taper-simulation"
    assert len(data["alternative_ids"]) == 2
    assert "taper-simulation" not in data["alternative_ids"]
    assert "invalid-id" not in data["alternative_ids"]


def test_navigate_llm_exception_falls_back_gracefully(isolated_env, monkeypatch):
    monkeypatch.setattr(assistant_mod.llm_client, "_get_client", lambda: object())

    def failing_chat(*args, **kwargs):
        raise RuntimeError("DashScope timeout")

    monkeypatch.setattr(assistant_mod.llm_client, "chat_completion", failing_chat)

    res = isolated_env.post(
        "/api/assistant/navigate",
        json={"query": "我要绑定佳明手表", "user_roles": {"logged_in": True}},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["engine"] == "deterministic"
    assert data["primary_id"] == "bind-garmin"
    assert data["auto_navigate"] is True


def test_navigate_permission_denial_for_runner(isolated_env, monkeypatch):
    monkeypatch.setattr(assistant_mod.llm_client, "_get_client", lambda: None)

    runner_roles = {
        "logged_in": True,
        "is_coach_or_owner": False,
        "has_managed_org": False,
        "is_super_admin": False,
    }

    res_leader = isolated_env.post(
        "/api/assistant/navigate",
        json={"query": "我是教练，想导入Excel周训练课表", "user_roles": runner_roles},
    )
    assert res_leader.status_code == 200
    d_leader = res_leader.json()
    assert d_leader["primary_id"] == "import-schedule"
    assert d_leader["permission_ok"] is False
    assert d_leader["auto_navigate"] is False
    assert "create-club" in d_leader["alternative_ids"]

    res_org = isolated_env.post(
        "/api/assistant/navigate",
        json={"query": "审核大群实名花名册", "user_roles": runner_roles},
    )
    assert res_org.status_code == 200
    d_org = res_org.json()
    assert d_org["primary_id"] == "org-roster-audit"
    assert d_org["permission_ok"] is False
    assert d_org["auto_navigate"] is False
    assert "join-org" in d_org["alternative_ids"]

    res_super = isolated_env.post(
        "/api/assistant/navigate",
        json={"query": "打开平台超管遥测大盘", "user_roles": runner_roles},
    )
    assert res_super.status_code == 200
    d_super = res_super.json()
    assert d_super["primary_id"] == "admin-analytics"
    assert d_super["permission_ok"] is False
    assert d_super["auto_navigate"] is False


def test_navigate_auth_requirement_and_empty_query(isolated_env, monkeypatch):
    monkeypatch.setattr(assistant_mod.llm_client, "_get_client", lambda: None)

    res_protected = isolated_env.post(
        "/api/assistant/navigate",
        json={"query": "我要绑定佳明手表", "user_roles": {"logged_in": False}},
    )
    assert res_protected.status_code == 200
    assert res_protected.json()["primary_id"] == "bind-garmin"
    assert res_protected.json()["requires_auth"] is True

    res_public = isolated_env.post(
        "/api/assistant/navigate",
        json={"query": "看看新用户操作手册", "user_roles": {"logged_in": False}},
    )
    assert res_public.status_code == 200
    assert res_public.json()["primary_id"] == "manual-guide"
    assert res_public.json()["requires_auth"] is False

    res_plaza = isolated_env.post(
        "/api/assistant/navigate",
        json={"query": "看看名帅教练风采展厅", "user_roles": {"logged_in": False}},
    )
    assert res_plaza.status_code == 200
    assert res_plaza.json()["primary_id"] == "showcase-plaza"
    assert res_plaza.json()["requires_auth"] is False

    res_empty = isolated_env.post(
        "/api/assistant/navigate",
        json={"query": "   "},
    )
    assert res_empty.status_code == 400


def test_transcribe_paraformer_primary_success(isolated_env, monkeypatch):
    monkeypatch.setattr(settings, "DASHSCOPE_API_KEY", "sk-test-valid-key-123456")

    class FakeRecognition:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def call(self, file_path):
            assert file_path.endswith(".wav")
            return SimpleNamespace(
                status_code=200,
                get_sentence=lambda: [{"text": "我要绑定佳明手表"}],
            )

    fake_asr_mod = types.ModuleType("dashscope.audio.asr")
    fake_asr_mod.Recognition = FakeRecognition
    fake_audio_mod = types.ModuleType("dashscope.audio")
    fake_audio_mod.asr = fake_asr_mod
    fake_ds = types.ModuleType("dashscope")
    fake_ds.api_key = ""
    fake_ds.audio = fake_audio_mod
    fake_ds.MultiModalConversation = SimpleNamespace(call=lambda **kw: None)

    monkeypatch.setitem(sys.modules, "dashscope", fake_ds)
    monkeypatch.setitem(sys.modules, "dashscope.audio", fake_audio_mod)
    monkeypatch.setitem(sys.modules, "dashscope.audio.asr", fake_asr_mod)

    wav_bytes = _make_minimal_wav_bytes()
    # Explicitly send no Authorization header to confirm PUBLIC_PATHS allows unauthenticated voice use
    res = isolated_env.post(
        "/api/assistant/transcribe",
        files={"audio": ("voice.wav", io.BytesIO(wav_bytes), "audio/wav")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["text"] == "我要绑定佳明手表"
    assert data["engine"] == "paraformer-realtime-v2"


def test_transcribe_fallback_to_qwen3_asr_flash(isolated_env, monkeypatch):
    monkeypatch.setattr(settings, "DASHSCOPE_API_KEY", "sk-test-valid-key-123456")

    class FailingRecognition:
        def __init__(self, **kwargs):
            pass

        def call(self, file_path):
            raise RuntimeError("paraformer websocket error")

    class FakeMultiModal:
        @staticmethod
        def call(**kwargs):
            return SimpleNamespace(
                status_code=200,
                output={
                    "choices": [
                        {
                            "message": {
                                "content": [{"text": "导入本周Excel课表"}],
                            }
                        }
                    ]
                },
            )

    fake_asr_mod = types.ModuleType("dashscope.audio.asr")
    fake_asr_mod.Recognition = FailingRecognition
    fake_audio_mod = types.ModuleType("dashscope.audio")
    fake_audio_mod.asr = fake_asr_mod
    fake_ds = types.ModuleType("dashscope")
    fake_ds.api_key = ""
    fake_ds.audio = fake_audio_mod
    fake_ds.MultiModalConversation = FakeMultiModal

    monkeypatch.setitem(sys.modules, "dashscope", fake_ds)
    monkeypatch.setitem(sys.modules, "dashscope.audio", fake_audio_mod)
    monkeypatch.setitem(sys.modules, "dashscope.audio.asr", fake_asr_mod)

    wav_bytes = _make_minimal_wav_bytes()
    res = isolated_env.post(
        "/api/assistant/transcribe",
        files={"audio": ("voice.wav", io.BytesIO(wav_bytes), "audio/wav")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["text"] == "导入本周Excel课表"
    assert data["engine"] == "qwen3-asr-flash"


def test_transcribe_validation_empty_and_oversized(isolated_env):
    res_empty = isolated_env.post(
        "/api/assistant/transcribe",
        files={"audio": ("empty.wav", io.BytesIO(b""), "audio/wav")},
    )
    assert res_empty.status_code == 400

    oversized = b"0" * (assistant_mod.MAX_AUDIO_BYTES + 10)
    res_big = isolated_env.post(
        "/api/assistant/transcribe",
        files={"audio": ("big.wav", io.BytesIO(oversized), "audio/wav")},
    )
    assert res_big.status_code == 413
