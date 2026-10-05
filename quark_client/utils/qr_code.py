#!/usr/bin/env python3
import os
import sys
import subprocess
from pathlib import Path

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


def display_qr_from_url(url: str):
    """生成二维码供用户扫码，三级回落：PNG（需 Pillow）→ SVG（纯 qrcode）→ 终端 ASCII。

    历史问题：本函数原先只写 PNG，而 PNG 依赖 Pillow；离线依赖包不含 Pillow，
    于是生成必然失败（只 warning 一句），用户实际只剩 ASCII 一条路。现补 SVG 回落 ——
    SVG 由 qrcode 直接生成、**不需要任何二进制依赖**，浏览器打开即可扫。
    另外输出目录改为 get_config_dir()，与 cookies.json 的落点保持一致
    （原先写死 ~/.quarkpan/config，与 get_cookies_file() 的默认目录不是同一个）。
    """
    logger = get_logger(__name__)
    from ..config import get_config_dir

    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)

    try:
        import qrcode

        # 1) 优先 PNG（装了 Pillow 时最省事）
        img_path = config_dir / 'qr_code.png'
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(url)
        qr.make(fit=True)
        qr.make_image(fill_color='black', back_color='white').save(str(img_path))
        print(f"✅ 二维码已生成: {img_path}")
        _open_image(str(img_path))
    except Exception as e:
        logger.warning(f"PNG 二维码生成失败（通常是环境没有 Pillow）: {e}")
        try:
            # 2) 回落 SVG —— 纯 qrcode，无二进制依赖
            import qrcode.image.svg

            svg_path = config_dir / 'qr_code.svg'
            qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage).save(str(svg_path))
            print(f"✅ 二维码已生成: {svg_path}（用浏览器打开后扫码）")
        except Exception as e2:
            logger.warning(f"SVG 二维码生成失败: {e2}")

    # 3) 终端 ASCII + 原始链接兜底
    print_ascii_qr(url)
    print(f"登录链接（可自行转成二维码）: {url}")
