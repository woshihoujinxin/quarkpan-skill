# -*- coding: utf-8 -*-
"""
文件下载服务
"""

import os
from typing import Callable, Dict, List, Optional

from ..core.api_client import QuarkAPIClient
from ..exceptions import APIError

# 桌面客户端 UA —— 用于绕过网页通道对 >50MB 文件的 23018 限制
# 参考: https://github.com/zhangjingwei/kuake_cli/pull/37
DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) quark-cloud-drive/2.5.56 Chrome/100.0.4896.160 "
    "Electron/18.3.5.12-a038f7b798 Safari/537.36 Channel/pckk_other_ch"
)
DESKTOP_PARAMS = {
    'pr': 'ucpro',
    'fr': 'pc',
    'sys': 'win32',
    've': '2.5.56',
    'ut': '',
    'guid': '',
}
_DOWNLOAD_BASE_URL = 'https://drive-pc.quark.cn/1/clouddrive'


class FileDownloadService:
    """文件下载服务"""

    def __init__(self, client: QuarkAPIClient):
        """
        初始化文件下载服务

        Args:
            client: API客户端实例
        """
        self.client = client

    def get_download_url(self, file_id: str) -> str:
        """
        获取文件下载链接

        大文件（>50MB）网页通道会返回 23018（download file size limit），
        此时自动改用桌面客户端标识重试，即可拿到可用下载链接。

        Args:
            file_id: 文件ID

        Returns:
            下载链接
        """
        data = {'fids': [file_id]}

        # 通道1：普通网页标识
        try:
            response = self.client.post(
                'file/download',
                json_data=data,
                params={'pr': 'ucpro', 'fr': 'pc'},
                base_url=_DOWNLOAD_BASE_URL
            )
            url = self._extract_url(response)
            if url:
                return url
        except Exception as e:
            if '23018' not in str(e) and 'download file size limit' not in str(e):
                raise

        # 通道2：桌面客户端标识（大文件通道）
        # 注意：httpx 客户端级 headers 会覆盖请求级 UA，必须临时替换客户端默认头
        response = self._post_as_desktop(data)
        url = self._extract_url(response)
        if url:
            return url

        raise APIError("无法获取下载链接")

    def _post_as_desktop(self, data: Dict) -> Dict:
        """以桌面客户端标识请求 file/download（用于绕过 >50MB 的 23018 限制）

        httpx 的**客户端级 headers 优先级高于请求级 headers**，所以只改请求头
        里的 User-Agent 无效。这里用干净的 headers 构造临时 httpx.Client，
        保证客户端级 UA 就是桌面客户端标识；请求完即关闭，不污染主客户端。

        参考: https://github.com/zhangjingwei/kuake_cli/pull/37
        """
        import time
        import httpx
        from ..config import Config, get_default_headers

        client = self.client
        headers = dict(get_default_headers())
        # ⚠️ get_default_headers() 返回小写 'user-agent'，若直接新增 'User-Agent'
        # 会与它共存；httpx 规范化时保留先到的小写键 → 桌面 UA 被丢弃。
        # 必须先删除默认键，再设桌面 UA。
        for k in [k for k in headers if k.lower() == 'user-agent']:
            del headers[k]
        headers['User-Agent'] = DESKTOP_UA
        # Cookie 存在 api_client 上（self.client 本身通常没有 cookies 属性）
        cookies = getattr(client, 'cookies', None) or getattr(
            getattr(client, 'api_client', None), 'cookies', None)
        if cookies:
            headers['cookie'] = cookies

        params = dict(DESKTOP_PARAMS)
        params.update({'__t': int(time.time() * 1000), '__dt': 1000})
        url = f'{_DOWNLOAD_BASE_URL}/file/download'

        with httpx.Client(timeout=Config.REQUEST_TIMEOUT,
                          headers=headers, follow_redirects=True) as tmp:
            resp = tmp.post(url, params=params, json=data)

        if resp.status_code >= 400:
            raise APIError(f"HTTP错误: {resp.status_code}, 响应: {resp.text[:300]}",
                           status_code=resp.status_code)
        return resp.json()

    @staticmethod
    def _extract_url(response) -> str:
        """从 download 响应中解析 download_url（兼容同步数组 / 异步对象）"""
        if not isinstance(response, dict):
            return ''
        data = response.get('data')
        if isinstance(data, list) and data:
            return data[0].get('download_url', '') or ''
        if isinstance(data, dict):
            # 异步任务：task_resp.data[0].download_url
            task_resp = data.get('task_resp') or {}
            inner = task_resp.get('data')
            if isinstance(inner, list) and inner:
                return inner[0].get('download_url', '') or ''
            return data.get('download_url', '') or ''
        return ''

    def get_download_urls(self, file_ids: List[str]) -> Dict[str, str]:
        """
        批量获取文件下载链接

        Args:
            file_ids: 文件ID列表

        Returns:
            文件ID到下载链接的映射字典
        """
        # 添加必要的查询参数
        params = {
            'pr': 'ucpro',
            'fr': 'pc',
            'uc_param_str': ''
        }

        data = {'fids': file_ids}

        try:
            response = self.client.post('file/download', json_data=data, params=params)
        except Exception as e:
            # 大文件走桌面客户端通道
            if '23018' in str(e) or 'download file size limit' in str(e):
                response = self._post_as_desktop(data)
            else:
                raise

        # 解析下载链接
        download_urls = {}
        if isinstance(response, dict) and 'data' in response:
            data_list = response['data']
            for download_info in data_list:
                fid = download_info.get('fid', '')
                download_url = download_info.get('download_url', '')
                if fid and download_url:
                    download_urls[fid] = download_url

        return download_urls

    def download_file(
        self,
        file_id: str,
        save_path: Optional[str] = None,
        chunk_size: int = 8192,
        progress_callback: Optional[Callable] = None
    ) -> str:
        """
        下载文件

        Args:
            file_id: 文件ID
            save_path: 保存路径，如果为None则使用文件原名
            chunk_size: 下载块大小
            progress_callback: 进度回调函数 (downloaded_bytes, total_bytes)

        Returns:
            实际保存的文件路径
        """

        # 使用与 reference.py 完全相同的参数
        params = {
            'pr': 'ucpro',
            'fr': 'pc',
            'sys': 'win32',
            've': '2.5.56',
            'ut': '',
            'guid': '',
        }

        data = {'fids': [file_id]}

        # 获取下载链接 + 文件信息（大文件自动走桌面客户端通道）
        try:
            response = self.client.post(
                'file/download',
                json_data=data,
                params={'pr': 'ucpro', 'fr': 'pc'},
                base_url=_DOWNLOAD_BASE_URL
            )
            if not self._extract_url(response):
                raise APIError('empty download_url')
        except Exception as e:
            if '23018' not in str(e) and 'empty download_url' not in str(e) \
                    and 'download file size limit' not in str(e):
                raise
            response = self._post_as_desktop(data)

        # 解析下载链接和文件信息
        if isinstance(response, dict) and 'data' in response:
            data_list = response['data']
            if data_list and len(data_list) > 0:
                download_info = data_list[0]
                download_url = download_info.get('download_url', '')
                file_name = download_info.get('file_name', f'file_{file_id}')
                _ = download_info.get('size', 0)  # file_size 暂时未使用
            else:
                raise APIError("无法获取下载信息")
        else:
            raise APIError("无法获取下载信息")

        if not download_url:
            raise APIError("无法获取下载链接")

        # 确定保存路径
        if save_path is None:
            save_path = file_name
        elif os.path.isdir(save_path):
            save_path = os.path.join(save_path, file_name)

        # 此时 save_path 不会是 None
        assert save_path is not None

        # 创建目录
        save_dir = os.path.dirname(save_path)
        if save_dir:
            os.makedirs(save_dir, exist_ok=True)

        # 下载文件，使用与API客户端相同的session和完整的headers
        download_headers = {
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Referer': 'https://pan.quark.cn/',
            'Origin': 'https://pan.quark.cn',
            'Sec-Ch-Ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
            'Sec-Ch-Ua-Mobile': '?1',
            'Sec-Ch-Ua-Platform': '"Android"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36'
        }

        # 尝试多种下载方式
        success = False

        # 方法1: 使用API客户端的session
        try:
            with self.client._client.stream('GET', download_url,  # type: ignore[attr-defined]
                                            headers=download_headers) as response:
                response.raise_for_status()
                success = True

                # 获取文件大小
                total_size = int(response.headers.get('content-length', 0))
                downloaded_size = 0

                with open(save_path, 'wb') as f:
                    for chunk in response.iter_bytes(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)

                            # 调用进度回调
                            if progress_callback:
                                progress_callback(downloaded_size, total_size)
        except Exception as e:
            # 第一种方法失败是正常的，静默切换到备用方法
            if "403" in str(e) or "Forbidden" in str(e):
                # 403错误是预期的，不显示错误信息
                pass
            else:
                # 其他错误可能需要用户知道
                print(f"下载方法1遇到问题，正在尝试备用方法...")
            success = False

        # 方法2: 如果方法1失败，尝试使用外部httpx客户端
        if not success:
            try:
                import httpx

                # 从API客户端获取cookies
                cookie_dict = {}
                if hasattr(self.client._client, 'cookies'):
                    for cookie in self.client._client.cookies.jar:  # type: ignore[attr-defined]
                        cookie_dict[cookie.name] = cookie.value

                # 添加cookies到headers
                if cookie_dict:
                    download_headers['Cookie'] = '; '.join([f'{k}={v}' for k, v in cookie_dict.items()])

                with httpx.stream('GET', download_url, headers=download_headers, timeout=60) as response:
                    response.raise_for_status()
                    success = True

                    # 获取文件大小
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded_size = 0

                    with open(save_path, 'wb') as f:
                        for chunk in response.iter_bytes(chunk_size=chunk_size):
                            if chunk:
                                f.write(chunk)
                                downloaded_size += len(chunk)

                                # 调用进度回调
                                if progress_callback:
                                    progress_callback(downloaded_size, total_size)
            except Exception as e:
                print(f"方法2失败: {e}")
                success = False

        if not success:
            raise APIError("所有下载方法都失败了，可能是夸克网盘的反爬虫机制")

        return save_path

    def download_files(
        self,
        file_ids: List[str],
        save_dir: str = "downloads",
        chunk_size: int = 8192,
        progress_callback: Optional[Callable] = None
    ) -> List[str]:
        """
        批量下载文件

        Args:
            file_ids: 文件ID列表
            save_dir: 保存目录
            chunk_size: 下载块大小
            progress_callback: 进度回调函数 (current_file, total_files, file_progress)

        Returns:
            下载的文件路径列表
        """

        os.makedirs(save_dir, exist_ok=True)
        downloaded_files = []

        for i, file_id in enumerate(file_ids, 1):
            try:
                def file_progress(downloaded, total):
                    if progress_callback:
                        progress_callback(i, len(file_ids), downloaded, total)

                file_path = self.download_file(
                    file_id,
                    save_dir,
                    chunk_size,
                    file_progress
                )
                downloaded_files.append(file_path)

            except Exception as e:
                print(f"下载文件 {file_id} 失败: {e}")
                continue

        return downloaded_files
