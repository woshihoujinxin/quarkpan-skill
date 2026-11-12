"""二维码弹窗开关契约测试（默认不弹，只能显式开启）。

背景（2026-11-12）：`display_qr_from_url(open_viewer=True)` 是默认值，
而 `auth/api_login.py` 调它时不传参；`QuarkAPIClient(auto_login=True)`
在**构造阶段**就进入登录流程。于是 `quarkpan ls` / `quarkpan status`
这类只读查询会在用户屏幕上凭空弹出二维码 PNG，并阻塞等扫码。
本文件把「默认不打开看图程序」钉死。
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quark_client.utils import qr_code  # noqa: E402

SAMPLE_URL = "https://b.quark.cn/apps/qklogin/pages/login/verifyLogin?token=abc123"


class TestQrViewerGate(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._env = {
            "QUARK_CONFIG_DIR": self._tmp.name,
        }
        patcher = mock.patch.dict(os.environ, self._env, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)
        os.environ.pop("QUARKPAN_QR_OPEN", None)
        # 终端 ASCII 会刷屏，测试里替换掉
        ascii_patcher = mock.patch.object(qr_code, "print_ascii_qr")
        ascii_patcher.start()
        self.addCleanup(ascii_patcher.stop)

    def test_默认不打开系统看图程序(self):
        with mock.patch.object(qr_code, "_open_image") as m:
            path = qr_code.display_qr_from_url(SAMPLE_URL)
            m.assert_not_called()
        self.assertIsNotNone(path)
        self.assertTrue(os.path.exists(path))

    def test_环境变量为1时才打开(self):
        os.environ["QUARKPAN_QR_OPEN"] = "1"
        with mock.patch.object(qr_code, "_open_image") as m:
            qr_code.display_qr_from_url(SAMPLE_URL)
            m.assert_called_once()

    def test_显式传参优先于环境变量(self):
        os.environ.pop("QUARKPAN_QR_OPEN", None)
        with mock.patch.object(qr_code, "_open_image") as m:
            qr_code.display_qr_from_url(SAMPLE_URL, open_viewer=True)
            m.assert_called_once()

    def test_显式关闭不被环境变量推翻(self):
        os.environ["QUARKPAN_QR_OPEN"] = "1"
        with mock.patch.object(qr_code, "_open_image") as m:
            qr_code.display_qr_from_url(SAMPLE_URL, open_viewer=False)
            m.assert_not_called()

    def test_开关函数只认肯定值(self):
        for v in ("0", "false", "no", "off", ""):
            os.environ["QUARKPAN_QR_OPEN"] = v
            self.assertFalse(qr_code._qr_viewer_enabled(), v)
        for v in ("1", "true", "YES", "on"):
            os.environ["QUARKPAN_QR_OPEN"] = v
            self.assertTrue(qr_code._qr_viewer_enabled(), v)


if __name__ == "__main__":
    unittest.main()
