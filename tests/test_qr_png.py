"""二维码 PNG 契约测试（格式定死 PNG，且零第三方依赖）。

背景（2026-10-05）：原实现「PNG（需 Pillow）→ SVG 回落」，离线包不含 Pillow，
于是实际总产 SVG，Agent 还得另想办法转成可在对话里展示的位图，白多花一轮。
现改为纯标准库直写 PNG，不再有回落分支。本文件把该契约钉死。
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import qrcode  # noqa: E402

from quark_client.utils.qr_png import (  # noqa: E402
    is_valid_png,
    read_gray_png,
    write_gray_png,
    write_matrix_png,
    write_qr_png,
)

SAMPLE_URL = "https://b.quark.cn/apps/qklogin/pages/login/verifyLogin?token=abc123DEF456"


class TestPngWriter(unittest.TestCase):
    def test_写出的文件是合法_png_且尺寸正确(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.png")
            write_gray_png(path, 4, 3, bytes([0] * 12))
            self.assertTrue(is_valid_png(path))
            w, h, px = read_gray_png(path)
            self.assertEqual((w, h), (4, 3))
            self.assertEqual(len(px), 12)

    def test_像素数据长度不符时明确报错(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                write_gray_png(os.path.join(d, "bad.png"), 4, 3, bytes([0] * 11))

    def test_签名正确且_IHDR_为_8bit_灰度(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "g.png")
            write_gray_png(path, 2, 2, bytes([0, 255, 255, 0]))
            with open(path, "rb") as fh:
                blob = fh.read()
            self.assertEqual(blob[:8], b"\x89PNG\r\n\x1a\n")
            # IHDR 的 depth/colortype
            self.assertEqual(blob[24], 8)  # bit depth
            self.assertEqual(blob[25], 0)  # color type 0 = 灰度

    def test_矩阵渲染_黑白极性正确(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "m.png")
            # 2x2 模块，box=2 → 4x4 像素
            write_matrix_png(path, [[True, False], [False, True]], box_size=2)
            w, h, px = read_gray_png(path)
            self.assertEqual((w, h), (4, 4))
            self.assertEqual(px[0], 0)  # 左上 = 黑
            self.assertEqual(px[3], 255)  # 右上 = 白
            self.assertEqual(px[12], 255)  # 左下 = 白
            self.assertEqual(px[15], 0)  # 右下 = 黑


class TestQrPng(unittest.TestCase):
    def test_生成的二维码逐模块等于_qrcode_自带矩阵(self):
        """关键断言：渲染结果与 qrcode 的模块矩阵逐格一致 —— 保证「扫得出来」。"""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "qr.png")
            write_qr_png(path, SAMPLE_URL, box_size=10, border=4)
            self.assertTrue(is_valid_png(path))

            w, h, px = read_gray_png(path)
            qr = qrcode.QRCode(box_size=10, border=4)
            qr.add_data(SAMPLE_URL)
            qr.make(fit=True)
            matrix = qr.get_matrix()
            n = len(matrix)
            box = w // n
            self.assertEqual(w, h)
            self.assertEqual(box, 10)

            mismatch = 0
            for ry, row in enumerate(matrix):
                for cx, on in enumerate(row):
                    y = ry * box + box // 2
                    x = cx * box + box // 2
                    if (px[y * w + x] < 128) != on:
                        mismatch += 1
            self.assertEqual(mismatch, 0, "渲染结果与 qrcode 模块矩阵不一致，扫码会失败")

    def test_不依赖_Pillow_也不依赖_pypng(self):
        """离线包只有纯 Python wheel；Pillow / pypng 都不在依赖里，必须照样出图。"""
        self.assertNotIn("PIL", sys.modules, "测试进程不应已加载 Pillow")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "no_pil.png")
            write_qr_png(path, SAMPLE_URL)
            self.assertTrue(is_valid_png(path))
            self.assertNotIn("PIL", sys.modules, "不应因生成二维码而引入 Pillow")


class TestDisplayQrFromUrl(unittest.TestCase):
    """display_qr_from_url 的对外契约：只出 PNG，且打印机器可读路径。"""

    def _call(self, config_dir, url=SAMPLE_URL):
        """在临时 config 目录下调用 display_qr_from_url，返回 (返回值, 标准输出)。

        同时把 _open_image 换成空操作，避免测试时真的弹出系统看图程序。
        """
        import contextlib
        import io
        from pathlib import Path

        import quark_client.config as cfg
        import quark_client.utils.qr_code as qr_code

        saved_cfg = cfg.get_config_dir
        saved_open = qr_code._open_image
        cfg.get_config_dir = lambda: Path(config_dir)
        qr_code._open_image = lambda *a, **k: None
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                ret = qr_code.display_qr_from_url(url)
        finally:
            cfg.get_config_dir = saved_cfg
            qr_code._open_image = saved_open
        return ret, buf.getvalue()

    def test_产出_png_并打印_QR_PNG_PATH(self):
        with tempfile.TemporaryDirectory() as d:
            ret, out = self._call(d)
            self.assertIsNotNone(ret)
            self.assertEqual(os.path.abspath(ret), os.path.abspath(os.path.join(d, "qr_code.png")))
            self.assertTrue(os.path.exists(ret))
            self.assertTrue(is_valid_png(ret))
            self.assertIn(f"QR_PNG_PATH={ret}", out)

    def test_不产出任何_svg_文件(self):
        with tempfile.TemporaryDirectory() as d:
            ret, out = self._call(d)
            self.assertIsNotNone(ret)
            leftovers = [f for f in os.listdir(d) if f.endswith(".svg")]
            self.assertEqual(leftovers, [], "不应再生成 SVG")
            self.assertNotIn("SVG", out)

    def test_PNG_写出失败时返回_None_且不谎报成功(self):
        import contextlib
        import io
        from pathlib import Path

        import quark_client.config as cfg
        import quark_client.utils.qr_code as qr_code
        import quark_client.utils.qr_png as qr_png

        def _boom(*a, **k):
            raise RuntimeError("boom")

        with tempfile.TemporaryDirectory() as d:
            saved_cfg = cfg.get_config_dir
            saved_write = qr_png.write_qr_png
            saved_open = qr_code._open_image
            cfg.get_config_dir = lambda: Path(d)
            qr_png.write_qr_png = _boom
            qr_code._open_image = lambda *a, **k: None
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    ret = qr_code.display_qr_from_url(SAMPLE_URL)
            finally:
                cfg.get_config_dir = saved_cfg
                qr_png.write_qr_png = saved_write
                qr_code._open_image = saved_open

            self.assertIsNone(ret)
            self.assertFalse(os.path.exists(os.path.join(d, "qr_code.png")))
            self.assertEqual([f for f in os.listdir(d) if f.endswith(".svg")], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
