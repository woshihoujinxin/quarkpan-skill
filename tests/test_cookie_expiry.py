#!/usr/bin/env python3
"""锁定「cookies 整体过期时间」的判定契约。

背景缺陷（2026-10-05 实测）：夸克登录会同时下发**短命的追踪类 cookie**
（`_UP_F7E_8D_`，expires 仅 10 分钟）。旧实现取「所有 cookie 里最小的
expires」当作整体有效期，于是扫码登录后 **10 分钟**就被判为过期，
`_load_cookies()` 返回 None，用户被迫反复扫码 —— 表现就是「刚装好就掉登录」。

真正决定登录态的是 `__pus` / `__kp` / `__kps` / `__ktd` / `__uid`（实测约 14 天）。

运行：

    python3 -m unittest discover -s tests -v
"""

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quark_client.auth.login import QuarkAuth  # noqa: E402


def _cookie(name: str, expires: int):
    return {"name": name, "value": "x", "expires": expires}


def _auth() -> QuarkAuth:
    # 绕过 __init__（它会创建真实配置目录），本用例只测纯函数
    return QuarkAuth.__new__(QuarkAuth)


class CookieExpiryTest(unittest.TestCase):
    def test_01_short_lived_tracking_cookie_must_not_dominate(self):
        """核心回归：10 分钟的追踪 cookie 不能把整体有效期拉成 10 分钟。

        这就是线上症状的根因 —— 真实登录凭证还有 14 天，却因这个 cookie
        被判「已过期」。
        """
        now = int(time.time())
        cookies = [
            _cookie("_UP_F7E_8D_", now + 600),          # 10 分钟追踪 cookie
            _cookie("__pus", now + 14 * 24 * 3600),     # 真实凭证 14 天
            _cookie("_UP_6D1_64_", now + 86400),        # 23.7 小时
        ]

        exp = _auth()._get_cookies_expire_time(cookies)

        self.assertEqual(exp, now + 86400, "应取剔除短命 cookie 后的最小值")
        self.assertGreater(exp - now, 3600, "绝不能再落到 10 分钟量级")

    def test_02_real_quark_cookie_set_is_not_expired_after_login(self):
        """用实测的夸克 cookie 集合验证：登录后不应立刻被判过期。"""
        now = int(time.time())
        cookies = [
            _cookie("_UP_28A_52_", now + 7 * 24 * 3600),
            _cookie("_UP_6D1_64_", now + 85428),
            _cookie("_UP_F7E_8D_", now + 600),          # 短命
            _cookie("_UP_A4A_11_", now + 365 * 24 * 3600),
            _cookie("_UP_D_", now + 7 * 24 * 3600),
            _cookie("__pus", now + 14 * 24 * 3600),
            _cookie("__kp", now + 14 * 24 * 3600),
            _cookie("__kps", now + 14 * 24 * 3600),
            _cookie("__ktd", now + 14 * 24 * 3600),
            _cookie("__uid", now + 14 * 24 * 3600),
            _cookie("ctoken", -1),                      # 会话 cookie，应被忽略
        ]

        exp = _auth()._get_cookies_expire_time(cookies)
        data = {"cookies": cookies, "timestamp": now, "expires_at": exp}

        self.assertGreater(exp - now, 3600)
        self.assertFalse(_auth()._is_cookies_expired(data))

    def test_03_all_short_lived_falls_back_to_longest_with_floor(self):
        """全是短命 cookie 的罕见情况：取最长者并保底 1 小时，避免刚写就过期。"""
        now = int(time.time())
        cookies = [_cookie("a", now + 600), _cookie("b", now + 900)]

        exp = _auth()._get_cookies_expire_time(cookies)

        self.assertGreaterEqual(exp, now + 3600)

    def test_04_no_usable_expires_defaults_to_seven_days(self):
        """没有任何 expires（如只有 ctoken 这类会话 cookie）→ 保守 7 天。"""
        now = int(time.time())
        cookies = [_cookie("ctoken", -1), _cookie("x", 0)]

        exp = _auth()._get_cookies_expire_time(cookies)

        self.assertGreater(exp, now + 6 * 24 * 3600)

    def test_05_genuinely_expired_cookie_is_still_rejected(self):
        """负向对照：真的过期了必须仍被判为过期（不能为了修复而放宽到永不失效）。"""
        now = int(time.time())
        auth = _auth()

        fresh = {"expires_at": now + 3600, "timestamp": now, "cookies": []}
        self.assertFalse(auth._is_cookies_expired(fresh))

        stale = {"expires_at": now - 10, "timestamp": now - 99999, "cookies": []}
        self.assertTrue(auth._is_cookies_expired(stale))

    def test_06_expiry_is_derived_from_credentials_not_timestamp(self):
        """有效期必须来自 cookie 的 expires，而不是简单地 timestamp+10min。"""
        now = int(time.time())
        cookies = [_cookie("__pus", now + 14 * 24 * 3600)]

        exp = _auth()._get_cookies_expire_time(cookies)

        self.assertEqual(exp, now + 14 * 24 * 3600)

    def test_07_stale_cached_expires_at_is_recalculated(self):
        """旧文件里缓存的 expires_at（历史错误算法写入）不得把有效凭证判死。

        场景：用户此前用旧版登录，文件里 expires_at 已被写成「10 分钟后」，
        但 cookie 本身还有 14 天。修复后必须能**就地重算**救活，无需重新扫码。
        """
        now = int(time.time())
        cookies = [_cookie("__pus", now + 14 * 24 * 3600)]
        data = {
            "cookies": cookies,
            "timestamp": now - 3600,
            "expires_at": now - 60,  # 旧算法留下的已过期值
        }

        self.assertFalse(_auth()._is_cookies_expired(data))

    def test_08_empty_cookies_still_uses_cached_value(self):
        """没有任何 cookie 时无法重算，仍按缓存 expires_at 判定（不能恒判不过期）。"""
        now = int(time.time())
        self.assertTrue(
            _auth()._is_cookies_expired({"cookies": [], "expires_at": now - 1, "timestamp": now - 1})
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
