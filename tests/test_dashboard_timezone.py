from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from pix_web.dashboard import _business_day_start
from pix_web.system_settings import _parse_timezone

UTC8 = timezone(timedelta(hours=8))


class BusinessDayStartTests(unittest.TestCase):
    """复现订单少一笔的时区根因：'今天' 必须按业务时区（UTC+8）算，而不是 UTC 零点。

    新加坡用户早上（00:00–08:00 SGT）支付的订单，paid_at 落在 UTC 的'昨天'，
    旧 _utc_day_start() 会把它排除在'今天'外。
    """

    def test_utc8_morning_order_counts_as_today(self) -> None:
        # 现在 15:00 SGT（07:00 UTC）。今天起点应是 2026-06-17 00:00 SGT = 2026-06-16 16:00 UTC。
        now = datetime(2026, 6, 17, 7, 0, tzinfo=timezone.utc)
        start = _business_day_start(UTC8, now=now)
        self.assertEqual(start, datetime(2026, 6, 16, 16, 0, tzinfo=timezone.utc))
        # 一笔早上 02:00 SGT（前一日 18:00 UTC）支付的订单，应 >= 今天起点（被计入）。
        morning_paid = datetime(2026, 6, 16, 18, 0, tzinfo=timezone.utc)
        self.assertGreaterEqual(morning_paid, start)

    def test_utc_zone_uses_utc_midnight(self) -> None:
        now = datetime(2026, 6, 17, 7, 0, tzinfo=timezone.utc)
        start = _business_day_start(timezone.utc, now=now)
        self.assertEqual(start, datetime(2026, 6, 17, 0, 0, tzinfo=timezone.utc))

    def test_late_utc_evening_rolls_to_next_local_day(self) -> None:
        # 20:00 UTC = 次日 04:00 SGT，今天起点应是 2026-06-18 00:00 SGT = 2026-06-17 16:00 UTC。
        now = datetime(2026, 6, 17, 20, 0, tzinfo=timezone.utc)
        start = _business_day_start(UTC8, now=now)
        self.assertEqual(start, datetime(2026, 6, 17, 16, 0, tzinfo=timezone.utc))


class ParseTimezoneTests(unittest.TestCase):
    def test_named_zone(self) -> None:
        tz = _parse_timezone("Asia/Shanghai")
        self.assertEqual(tz.utcoffset(datetime(2026, 6, 17, 12, 0)), timedelta(hours=8))

    def test_empty_defaults_to_utc8(self) -> None:
        self.assertEqual(_parse_timezone("").utcoffset(datetime(2026, 6, 17)), timedelta(hours=8))

    def test_invalid_falls_back_to_utc8(self) -> None:
        self.assertEqual(_parse_timezone("Not/AReal/Zone").utcoffset(datetime(2026, 6, 17)), timedelta(hours=8))


if __name__ == "__main__":
    unittest.main()
