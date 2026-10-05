#!/usr/bin/env python3
"""锁定「扫码登录必须落盘 cookies」的契约。

背景缺陷（2026-10-05 客户反馈）：APILogin 走完扫码流程后**从不**写 cookies.json
—— 落盘逻辑只存在于 QuarkAuth._save_cookies（即 `quarkpan auth login` 那条路径）。
于是凡走「直接 new APILogin() + wait_for_login()」的路径（安装说明与技能脚本原先
正是这么写的），扫码成功后全盘找不到 cookies.json，`quarkpan auth status` 永远报未登录。

这些用例保证该行为不再回退。运行：

    python3 -m unittest discover -s tests -v
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class LoginPersistenceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = os.environ.get("QUARK_CONFIG_DIR")
        # get_cookies_file() 在**调用时**读该环境变量，故无需重载模块即可生效
        os.environ["QUARK_CONFIG_DIR"] = self._tmp.name

    def tearDown(self):
        if self._old is None:
            os.environ.pop("QUARK_CONFIG_DIR", None)
        else:
            os.environ["QUARK_CONFIG_DIR"] = self._old
        self._tmp.cleanup()

    def _cookies_path(self) -> Path:
        return Path(self._tmp.name) / "cookies.json"

    def test_01_cookies_path_follows_config_dir(self):
        """QUARK_CONFIG_DIR 必须能重定向 cookies 落点（测试隔离的前提）。"""
        from quark_client.config import get_cookies_file

        self.assertEqual(str(get_cookies_file()), str(self._cookies_path()))

    def test_02_save_cookies_writes_and_reloads(self):
        """_save_cookies 写的文件，QuarkAuth._load_cookies 必须能读回（格式一致）。"""
        from quark_client.auth.api_login import APILogin
        from quark_client.auth.login import QuarkAuth

        login = APILogin(timeout=5)
        login.client.cookies.set("__pus", "abc", domain="pan.quark.cn")
        login.client.cookies.set("__puus", "def", domain="pan.quark.cn")
        login._save_cookies()

        self.assertTrue(self._cookies_path().is_file(), "cookies.json 未写出")
        data = json.loads(self._cookies_path().read_text(encoding="utf-8"))
        self.assertIn("cookies", data)
        self.assertIn("__pus", {c["name"] for c in data["cookies"]})

        loaded = QuarkAuth(timeout=5)._load_cookies()
        self.assertIsNotNone(loaded, "QuarkAuth 读不回 APILogin 写的 cookies")
        self.assertIn("__pus", {c["name"] for c in loaded["cookies"]})

    def test_03_process_login_result_persists(self):
        """扫码成功后 _process_login_result 必须落盘（跳过网络兑换那一步）。"""
        from quark_client.auth.api_login import APILogin

        login = APILogin(timeout=5)

        def _fake_exchange(service_ticket):  # 模拟服务端已把 cookie 设到 client 上
            login.client.cookies.set("__pus", "xyz", domain="pan.quark.cn")

        login._get_user_info_and_cookies = _fake_exchange
        login._process_login_result({"data": {"members": {"service_ticket": "ST"}}})

        self.assertTrue(
            self._cookies_path().is_file(),
            "_process_login_result 未落盘 cookies —— 登录状态判定会永远失败",
        )

    def test_04_missing_service_ticket_does_not_write(self):
        """拿不到 service ticket 时不应写出半成品 cookies.json。"""
        from quark_client.auth.api_login import APILogin

        login = APILogin(timeout=5)
        login._process_login_result({"data": {}})
        self.assertFalse(self._cookies_path().is_file())

    def test_05_no_reachable_code_after_default_return(self):
        """get_cookies_file 的源码里不应再有「第 8 条 return 之后还挂第 9 条」的死代码。"""
        import inspect

        from quark_client import config

        src = inspect.getsource(config.get_cookies_file)
        tail = src.split("return user_cookies", 1)
        self.assertEqual(
            len(tail), 2, "get_cookies_file 里找不到 `return user_cookies` 默认返回"
        )
        after = tail[1]
        self.assertNotIn(
            "legacy_path", after,
            "默认 return 之后仍存在不可达的 legacy fallback 死代码",
        )


    def test_06_wait_for_login_persists_end_to_end(self):
        """走 wait_for_login（客户/安装说明实际调用的入口）也必须落盘。"""
        from unittest.mock import patch

        from quark_client.auth.api_login import APILogin

        login = APILogin(timeout=5)
        # 模拟「第一次轮询就扫码成功」。注意 _is_login_success 的判据是
        # status==2000000 且 message=="ok" 且存在 data.members.service_ticket。
        login.check_login_status = lambda token: {
            "status": 2000000,
            "message": "ok",
            "data": {"members": {"service_ticket": "ST"}},
        }
        login._get_user_info_and_cookies = lambda st: login.client.cookies.set(
            "__pus", "from-wait", domain="pan.quark.cn"
        )
        login._show_countdown = lambda s: None
        login._stop_countdown_display = lambda: None

        with patch("quark_client.auth.api_login.time.sleep", lambda s: None):
            ok = login.wait_for_login("fake-token")

        self.assertTrue(ok)
        self.assertTrue(
            self._cookies_path().is_file(),
            "wait_for_login 未落盘 cookies —— 这正是客户遇到的「扫码成功但报未登录」",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
