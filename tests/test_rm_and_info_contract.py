"""`rm` / `rename` / `fileinfo` 的两个硬契约回归测试。

背景（2026-10-05 真机实测两个坑，都是「静默出错、极难排查」型）：

🔴 坑 1 —— `quarkpan rm` 不带 `-f` 在非交互环境**永久挂死**
   stdin 是「已打开但永不写入」的管道（Agent / CI 常见）时，`rich.prompt.Confirm.ask()`
   一直阻塞等输入 → 直到被 SIGTERM（现象：exit 137、零输出、看着像网络卡住）；
   stdin 是 /dev/null 时则抛 `EOF when reading a line`，被包装成「删除失败」这种**误导性**报错。
   修法：破坏性命令先判 `is_interactive()`，非交互且未给 `-f` → 快速失败（退出码 2）。

🔴 坑 2 —— 删除/重命名**预览显示成别的文件**（张冠李戴）
   旧实现的详情接口是 `GET file?fids=<fid>`；该端点只认 `pdir_fid`（列目录语义），
   `fids` 被服务端**静默忽略**并回落成「根目录列表」，再被「没匹配到就 return file_list[0]」
   的兜底吞掉 → 返回**根目录第一条**。
   实测症状：删某 zip 的 fid，预览打印 `文件夹: workbuddy-闲鱼自动化`，看着像要删整个文件夹。
   修法：改用 `GET file/info?fid=<fid>`，并**彻底删掉「返回第一条」的兜底**。

本文件把这两条契约钉死，防止后续 AI/人「顺手简化」时回退。
"""

import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quark_client.cli.commands import basic_fileops  # noqa: E402
from quark_client.cli import utils as cli_utils  # noqa: E402
from quark_client.services.file_service import FileService  # noqa: E402

TARGET_FID = "44201e59569a4c8abe0cc661dc8b781c"
OTHER_FID = "d4ca6dbe69d94f3ab24d52fb8d612e51"   # 根目录第一条（父文件夹）
ROOT_LISTING = [
    {"fid": OTHER_FID, "file_name": "workbuddy-闲鱼自动化", "file_type": 0},
    {"fid": "2ce04c80a0fd4b05b3e8efdf2e880dc1", "file_name": "网盘拉新", "file_type": 0},
]


class FakeApi:
    """记录调用的假 API 客户端"""

    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, path, params=None, **kwargs):
        self.calls.append((path, params))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


# --------------------------------------------------------------------------
# 坑 2：get_file_info 的端点/参数/兜底契约
# --------------------------------------------------------------------------
class TestGetFileInfoContract(unittest.TestCase):
    def _svc(self, response):
        api = FakeApi(response)
        return FileService(api), api

    def test_端点必须是_file_info_且参数名是_fid(self):
        svc, api = self._svc({"status": 200, "data": {"fid": TARGET_FID, "file_name": "x.zip"}})
        svc.get_file_info(TARGET_FID)
        self.assertEqual(1, len(api.calls))
        path, params = api.calls[0]
        self.assertEqual("file/info", path)
        self.assertEqual({"fid": TARGET_FID}, params)
        # 回归锁：绝不回到 file?fids=（服务端会静默忽略该参数）
        self.assertNotIn("fids", params)

    def test_精确返回目标文件(self):
        svc, _ = self._svc({"status": 200, "data": {"fid": TARGET_FID, "file_name": "x.zip", "file_type": 1}})
        info = svc.get_file_info(TARGET_FID)
        self.assertEqual(TARGET_FID, info["fid"])
        self.assertEqual("x.zip", info["file_name"])

    def test_绝不返回第一条兜底_根目录列表必须报错而非张冠李戴(self):
        """这是坑 2 的核心回归：拿到的是别人的列表时，必须报错，不能返回第一条。"""
        svc, _ = self._svc({"status": 200, "data": {"list": ROOT_LISTING}})
        with self.assertRaises(Exception) as ctx:
            svc.get_file_info(TARGET_FID)
        self.assertIn(TARGET_FID, str(ctx.exception))
        # 关键：绝不能把 OTHER_FID（根目录第一条）当结果返回
        self.assertFalse(isinstance(getattr(ctx.exception, "args", [None])[0], dict))

    def test_列表格式也只认精确命中(self):
        svc, _ = self._svc({"status": 200, "data": {"list": ROOT_LISTING + [
            {"fid": TARGET_FID, "file_name": "x.zip", "file_type": 1}]}})
        info = svc.get_file_info(TARGET_FID)
        self.assertEqual(TARGET_FID, info["fid"])

    def test_裸列表格式精确命中(self):
        svc, _ = self._svc({"status": 200, "data": [{"fid": TARGET_FID, "file_name": "x.zip"}]})
        self.assertEqual("x.zip", svc.get_file_info(TARGET_FID)["file_name"])

    def test_空_data_抛异常(self):
        for resp in ({"status": 200, "data": {}}, {"status": 200, "data": {"list": []}},
                     {"status": 200, "data": None}, {"status": 200}):
            with self.subTest(resp=resp):
                svc, _ = self._svc(resp)
                with self.assertRaises(Exception):
                    svc.get_file_info(TARGET_FID)

    def test_无效ID_抛_ValueError(self):
        for bad in ("", "0", None):
            with self.subTest(bad=bad):
                svc, api = self._svc({"status": 200, "data": {"fid": TARGET_FID}})
                with self.assertRaises(ValueError):
                    svc.get_file_info(bad)
                self.assertEqual([], api.calls, "无效 ID 不应发起请求")


# --------------------------------------------------------------------------
# 坑 1：非交互环境绝不阻塞
# --------------------------------------------------------------------------
class TestNonInteractiveConfirm(unittest.TestCase):
    def _no_ask(self):
        """Confirm.ask 一旦被调用就说明会阻塞 —— 直接判失败"""
        return mock.patch.object(cli_utils.Confirm, "ask",
                                 side_effect=AssertionError("非交互环境不应调用 Confirm.ask"))

    def test_非交互_未给force_快速失败退出码2(self):
        with mock.patch.object(cli_utils, "is_interactive", return_value=False), self._no_ask():
            with redirect_stdout(io.StringIO()) as buf:
                with self.assertRaises(SystemExit) as ctx:
                    cli_utils.ensure_confirm(False, "确定？", action="删除")
        self.assertEqual(2, ctx.exception.code)
        out = buf.getvalue()
        self.assertIn("-f", out)
        self.assertIn("未执行任何变更", out)
        # rich 用的是 [bold] 标记，不是 markdown 的 ** —— 别把星号原样打给用户
        self.assertNotIn("**", out)

    def test_非交互_给了force_直接放行且不问(self):
        with mock.patch.object(cli_utils, "is_interactive", return_value=False), self._no_ask():
            self.assertTrue(cli_utils.ensure_confirm(True, "确定？", action="删除"))

    def test_非交互_confirm_action_安全返回False不阻塞(self):
        with mock.patch.object(cli_utils, "is_interactive", return_value=False):
            with mock.patch.object(cli_utils.console, "input",
                                   side_effect=AssertionError("非交互环境不应读 stdin")):
                with redirect_stdout(io.StringIO()):
                    self.assertFalse(cli_utils.confirm_action("确定？"))

    def test_交互终端_正常透传用户答案(self):
        with mock.patch.object(cli_utils, "is_interactive", return_value=True):
            with mock.patch.object(cli_utils.Confirm, "ask", return_value=True):
                self.assertTrue(cli_utils.ensure_confirm(False, "确定？", action="删除"))
            with mock.patch.object(cli_utils.Confirm, "ask", return_value=False):
                self.assertFalse(cli_utils.ensure_confirm(False, "确定？", action="删除"))

    def test_is_interactive_无stdin时为False(self):
        with mock.patch.object(cli_utils.sys, "stdin", None):
            self.assertFalse(cli_utils.is_interactive())
        fake = mock.Mock()
        fake.isatty.return_value = False
        with mock.patch.object(cli_utils.sys, "stdin", fake):
            self.assertFalse(cli_utils.is_interactive())


# --------------------------------------------------------------------------
# delete_files 端到端（假 client）
# --------------------------------------------------------------------------
class FakeClient:
    def __init__(self, info=None):
        self.deleted = None
        self.deleted_by_name = None
        self._info = info or {"fid": TARGET_FID, "file_name": "xianyu-pipeline-1.0.0.zip", "file_type": 1}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def is_logged_in(self):
        return True

    def get_file_info(self, fid):
        return dict(self._info)

    def resolve_path(self, path, current_folder_id="0"):
        return TARGET_FID, "file"

    def delete_files(self, ids):
        self.deleted = list(ids)
        return {"status": 200}

    def delete_files_by_name(self, paths, current_folder_id="0"):
        self.deleted_by_name = list(paths)
        return {"status": 200}


class TestDeleteFilesCommand(unittest.TestCase):
    def _run(self, fake, force, paths=None, use_id=True):
        paths = paths or [TARGET_FID]
        with mock.patch.object(basic_fileops, "get_client", lambda auto_login=True: fake):
            with redirect_stdout(io.StringIO()) as buf:
                basic_fileops.delete_files(paths, force=force, use_id=use_id)
        return buf.getvalue()

    def test_非交互不加f_退出码2且一个删除请求都不发(self):
        fake = FakeClient()
        with mock.patch.object(cli_utils, "is_interactive", return_value=False):
            with mock.patch.object(cli_utils.Confirm, "ask",
                                   side_effect=AssertionError("不应阻塞询问")):
                with self.assertRaises(SystemExit) as ctx:
                    self._run(fake, force=False)
        self.assertEqual(2, ctx.exception.code)
        self.assertIsNone(fake.deleted, "非交互未确认时绝不能真的删除")

    def test_加f_正常删除(self):
        fake = FakeClient()
        out = self._run(fake, force=True)
        self.assertEqual([TARGET_FID], fake.deleted)
        self.assertIn("成功删除", out)

    def test_预览显示真实文件名与fid(self):
        """坑 2 的端到端回归：预览必须是目标文件自己的名字。"""
        fake = FakeClient()
        out = self._run(fake, force=True)
        self.assertIn("xianyu-pipeline-1.0.0.zip", out)
        self.assertNotIn("workbuddy-闲鱼自动化", out)
        self.assertIn(TARGET_FID, out)

    def test_详情读不到时显式告警而不是静默显示别人的名字(self):
        class Bad(FakeClient):
            def get_file_info(self, fid):
                raise RuntimeError("boom")

        fake = Bad()
        out = self._run(fake, force=True)
        self.assertIn("未能读取详情", out)
        self.assertNotIn("workbuddy-闲鱼自动化", out)

    def test_路径模式仍可用(self):
        fake = FakeClient()
        out = self._run(fake, force=True, paths=["workbuddy-闲鱼自动化/x.zip"], use_id=False)
        self.assertIsNotNone(fake.deleted_by_name)
        self.assertIn("成功删除", out)


# --------------------------------------------------------------------------
# fileinfo 命令的渲染回归：created_at / updated_at 是 int 时间戳，
# 直接塞进 rich Table 会抛 `unable to render int`（命令此前无人跑，坑一直没暴露）
# --------------------------------------------------------------------------
class TestFileInfoCommand(unittest.TestCase):
    def test_int时间戳也能正常渲染(self):
        info = {
            "fid": TARGET_FID,
            "file_name": "xianyu-pipeline-1.0.0.zip",
            "file_type": 1,
            "size": 35286873,
            "format_type": "zip",
            "created_at": 1791193800,
            "updated_at": 1791193900000,   # 毫秒级
        }
        fake = FakeClient(info=info)
        with mock.patch.object(basic_fileops, "get_client", lambda auto_login=True: fake):
            with redirect_stdout(io.StringIO()) as buf:
                basic_fileops.file_info(TARGET_FID)
        out = buf.getvalue()
        self.assertIn("xianyu-pipeline-1.0.0.zip", out)
        self.assertNotIn("unable to render", out)

    def test_缺失字段与None也不炸(self):
        for info in ({"fid": TARGET_FID},
                     {"fid": TARGET_FID, "file_name": "a", "size": None,
                      "format_type": None, "created_at": None, "updated_at": "?"},
                     {"fid": TARGET_FID, "file_name": "a", "size": "1234"}):
            with self.subTest(info=info):
                fake = FakeClient(info=info)
                with mock.patch.object(basic_fileops, "get_client", lambda auto_login=True: fake):
                    with redirect_stdout(io.StringIO()) as buf:
                        basic_fileops.file_info(TARGET_FID)
                self.assertNotIn("unable to render", buf.getvalue())


# --------------------------------------------------------------------------
# 版本号单一定义
# --------------------------------------------------------------------------
class TestVersionSingleSource(unittest.TestCase):
    def test_包版本与_pyproject_一致(self):
        import re
        import quark_client
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "pyproject.toml"), encoding="utf-8") as f:
            m = re.search(r'^version\s*=\s*"([^"]+)"', f.read(), re.M)
        self.assertIsNotNone(m, "pyproject.toml 里找不到 version")
        self.assertEqual(m.group(1), quark_client.__version__)


if __name__ == "__main__":
    unittest.main(verbosity=2)
