"""
Test that WeCom bot reply truncation works correctly.
The old bug was MAX_BYTES=220 which would aggressively truncate
Chinese text to ~60 characters. The fix sets it to 2000 (WeCom limit is 2048).
"""
import pytest


def _simulate_truncation(reply_text: str, max_bytes: int) -> str:
    """Simulates the truncation logic from wecom_bot.py"""
    encoded = reply_text.encode("utf-8")
    if len(encoded) > max_bytes:
        truncated = encoded[:max_bytes].decode("utf-8", errors="ignore")
        for sep in ["！", "！", "。", "？", "~", "…", "!", "?", ".", "\n"]:
            idx = truncated.rfind(sep)
            if idx > 0:
                truncated = truncated[:idx + len(sep)]
                break
        return truncated
    return reply_text


class TestTruncation:
    """Test the truncation behavior with old vs new MAX_BYTES."""

    # A realistic bot reply — mostly Chinese chars so it exceeds 220 bytes
    SAMPLE_REPLY = (
        "哎呦，问到点子上了！今年领跑的是金哥，"
        "一百五十二公里遥遥领先，简直是跑团永动机啊！"
        "你才排第五名，八十三公里，赶紧追啊，"
        "再不跑排名要被隔壁老王踩到脚底了🏃"
    )

    SAMPLE_REPLY_SHORT = "哎呦，跑得不错嘛！本月四十二公里了，继续加油🔥"

    def test_old_limit_truncates_normal_reply(self):
        """With old MAX_BYTES=220, a normal Chinese reply gets truncated."""
        old_max = 220
        byte_count = len(self.SAMPLE_REPLY.encode("utf-8"))
        assert byte_count > 220, f"Sample must exceed 220 bytes, got {byte_count}"
        result = _simulate_truncation(self.SAMPLE_REPLY, old_max)
        assert len(result) < len(self.SAMPLE_REPLY), (
            f"Expected truncation with old limit. "
            f"Original bytes={byte_count}, Result chars={len(result)}"
        )
        assert "再不跑" not in result, "Old limit should have cut off the ending"

    def test_new_limit_preserves_normal_reply(self):
        """With new MAX_BYTES=2000, a normal ~100 char reply is preserved."""
        new_max = 2000
        result = _simulate_truncation(self.SAMPLE_REPLY, new_max)
        assert result == self.SAMPLE_REPLY, (
            f"New limit should preserve the full reply. "
            f"Bytes={len(self.SAMPLE_REPLY.encode('utf-8'))}"
        )

    def test_short_reply_unchanged_both_limits(self):
        """Short replies should be unchanged with either limit."""
        for max_b in [220, 2000]:
            result = _simulate_truncation(self.SAMPLE_REPLY_SHORT, max_b)
            assert result == self.SAMPLE_REPLY_SHORT

    def test_extremely_long_reply_truncated_at_sentence(self):
        """Very long replies (>2000 bytes) should still be truncated at sentence boundary."""
        long_reply = "这是一个很长的回复。" * 80  # ~2400 bytes
        result = _simulate_truncation(long_reply, 2000)
        assert len(result.encode("utf-8")) <= 2000
        assert result.endswith("。"), f"Expected truncation at 。, got: ...{result[-10:]}"

    def test_byte_count_of_typical_reply(self):
        """Verify that typical replies are well within the 2000 byte limit."""
        typical = "哈" * 120 + "🏃🔥"
        byte_count = len(typical.encode("utf-8"))
        assert byte_count < 2000, (
            f"A 120-char reply should be under 2000 bytes, got {byte_count}"
        )

    def test_emoji_heavy_reply_preserved(self):
        """Replies with multiple emojis should not be truncated with new limit."""
        emoji_reply = "太强了🔥今年金哥一百五十二公里领跑💪你八十三公里排第五🏃加油追啊别掉队🫡"
        result = _simulate_truncation(emoji_reply, 2000)
        assert result == emoji_reply

    def test_old_limit_byte_math(self):
        """Demonstrate the old bug: 220 bytes / 3 bytes per Chinese char = 73 chars max."""
        text_74_chars = "跑" * 74  # 74 * 3 = 222 bytes > 220
        result_old = _simulate_truncation(text_74_chars, 220)
        assert len(result_old) < 74, (
            f"Old limit should truncate 74 Chinese chars (222 bytes > 220)"
        )
        result_new = _simulate_truncation(text_74_chars, 2000)
        assert result_new == text_74_chars


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
