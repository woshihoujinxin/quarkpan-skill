#!/usr/bin/env python3
import os
import sys
import subprocess
from pathlib import Path
from typing import Optional

from .logger import get_logger


def print_ascii_qr(text: str):
    logger = get_logger(__name__)
    try:
        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(text)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except Exception as e:
        logger.warning(f"ASCII QR render failed: {e}")


def display_qr_code(qr_image_path: str):
    logger = get_logger(__name__)
    qr_path = Path(qr_image_path)

    if not qr_path.exists():
        logger.error(f"二维码文件不存在: {qr_image_path}")
        return

    logger.info("二维码已生成，请使用夸克APP扫描")
    print(f"二维码文件位置: {qr_image_path}")


def _open_image(image_path: str):
    """用系统默认图片查看器打开"""
    try:
        if sys.platform == 'win32':
            os.startfile(image_path)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', image_path])
        else:
            subprocess.Popen(['xdg-open', image_path])
    except Exception as e:
        get_logger(__name__).warning(f"无法自动打开图片: {e}")


def display_qr_from_url(
    url: str,
    box_size: int = 10,
    border: int = 4,
    open_viewer: bool = True,
) -> Optional[str]:
    """生成二维码供用户扫码。

    🔴 **格式定死 PNG，不再有 SVG 分支**（2026-10-05 定稿）。

    历史教训：原实现「优先 PNG（依赖 Pillow）→ 失败回落 SVG」，而离线依赖包按设计
    不含 Pillow（见 pyproject 移除平台绑定 wheel 的注释），于是**实际总是产出 SVG**；
    Agent 拿到 SVG 还得再想办法转成能在对话里直接展示的位图，白白多花一轮。
    现在 PNG 由 `qr_png.write_qr_png()` 用**纯标准库（zlib + struct）直写**，
    不依赖 Pillow / pypng / 任何第三方，因此不存在「回落」——路径唯一、结果恒定。

    输出目录用 get_config_dir()，与 cookies.json 的落点保持一致
    （原先写死 ~/.quarkpan/config，与 get_cookies_file() 的默认目录不是同一个）。

    Args:
        box_size: 每个二维码模块的像素边长（越大越清晰、文件越大）。
        border: 四周留白模块数（QR 规范要求 >= 4，过小会影响识别率）。
        open_viewer: 是否调用系统看图程序打开（Agent / 无图形环境传 False）。

    Returns:
        生成的 PNG 绝对路径；连 PNG 都写不出时返回 None（此时只剩终端 ASCII 兜底）。
    """
    logger = get_logger(__name__)
    from ..config import get_config_dir
    from .qr_png import write_qr_png

    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)

    img_path = config_dir / 'qr_code.png'
    try:
        write_qr_png(str(img_path), url, box_size=box_size, border=border)
    except Exception as e:
        logger.warning(f"二维码 PNG 生成失败: {e}")
        print_ascii_qr(url)
        print(f"登录链接（可自行转成二维码）: {url}")
        return None

    print(f"✅ 二维码已生成（PNG）: {img_path}")
    # 机器可读行：Agent 直接取这一行去展示图片，不用猜路径
    print(f"QR_PNG_PATH={img_path}")
    if open_viewer:
        _open_image(str(img_path))

    # 终端 ASCII 作为并行兜底（无图形环境也能扫）
    print_ascii_qr(url)
    return str(img_path)
