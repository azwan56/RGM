"""
Test that WeCom bot reply truncation works correctly.
The WS stream reply API limit is 20480 bytes. MAX_BYTES is set to 20000.
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
    """Test the truncation behavior with the 20000-byte limit."""

    # A realistic bot reply — mostly Chinese chars
    SAMPLE_REPLY = (
        "哎呦，问到点子上了！今年领跑的是金哥，"
        "一百五十二公里遥遥领先，简直是跑团永动机啊！"
        "你才排第五名，八十三公里，赶紧追啊，"
        "再不跑排名要被隔壁老王踩到脚底了🏃"
    )

    SAMPLE_REPLY_SHORT = "哎呦，跑得不错嘛！本月四十二公里了，继续加油🔥"

    # A medium-length reply (~2000 bytes) that was truncated by the old limit
    SAMPLE_REPLY_MEDIUM = (
        "嘿嘿，本团宠查了一下你的跑步数据！"
        "这周你跑了四次，总计三十五公里，平均配速五分四十秒，"
        "最快的一次是周三的十公里，配速五分十五秒，简直是飞起来了！"
        "不过周五那次恢复跑有点慢啊，六分三十秒的配速是在散步吗？"
        "总体来说这周表现不错，但是距离你月跑量一百五十公里的目标还差得远呢，"
        "赶紧加油，别让隔壁老王超过你了！"
        "对了，提醒你一下，周末有个团练活动，记得来参加哦！"
    )

    def test_normal_reply_preserved(self):
        """Normal replies should be preserved with 20000-byte limit."""
        result = _simulate_truncation(self.SAMPLE_REPLY, 20000)
        assert result == self.SAMPLE_REPLY

    def test_medium_reply_preserved(self):
        """Medium-length replies (~600 bytes) should be preserved."""
        byte_count = len(self.SAMPLE_REPLY_MEDIUM.encode("utf-8"))
        assert byte_count > 500, f"Medium sample must exceed 500 bytes, got {byte_count}"
        result = _simulate_truncation(self.SAMPLE_REPLY_MEDIUM, 20000)
        assert result == self.SAMPLE_REPLY_MEDIUM

    def test_short_reply_unchanged(self):
        """Short replies should be unchanged."""
        result = _simulate_truncation(self.SAMPLE_REPLY_SHORT, 20000)
        assert result == self.SAMPLE_REPLY_SHORT

    def test_extremely_long_reply_truncated_at_sentence(self):
        """Very long replies (>20000 bytes) should still be truncated at sentence boundary."""
        long_reply = "这是一个很长的回复。" * 800  # ~24000 bytes
        result = _simulate_truncation(long_reply, 20000)
        assert len(result.encode("utf-8")) <= 20000
        assert result.endswith("。"), f"Expected truncation at 。, got: ...{result[-10:]}"

    def test_byte_count_of_typical_reply(self):
        """Verify that typical replies are well within the 20000-byte limit."""
        # Even a 2000-char Chinese reply is only ~6000 bytes
        typical = "哈" * 2000 + "🏃🔥"
        byte_count = len(typical.encode("utf-8"))
        assert byte_count < 20000, (
            f"A 2000-char reply should be under 20000 bytes, got {byte_count}"
        )

    def test_emoji_heavy_reply_preserved(self):
        """Replies with multiple emojis should not be truncated."""
        emoji_reply = "太强了🔥今年金哥一百五十二公里领跑💪你八十三公里排第五🏃加油追啊别掉队🫡"
        result = _simulate_truncation(emoji_reply, 20000)
        assert result == emoji_reply

    def test_old_limit_would_truncate(self):
        """Demonstrate that the old 2000-byte limit would truncate medium replies."""
        # 1000 Chinese chars = 3000 bytes > 2000 old limit
        text_1000_chars = "跑" * 1000
        result_old = _simulate_truncation(text_1000_chars, 2000)
        assert len(result_old) < 1000, "Old limit would have truncated"
        result_new = _simulate_truncation(text_1000_chars, 20000)
        assert result_new == text_1000_chars, "New limit should preserve"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
