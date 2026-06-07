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
    """生成二维码图片并用系统查看器打开，终端同时显示 ASCII 备用"""
    logger = get_logger(__name__)

    try:
        import qrcode
        config_dir = Path.home() / '.quarkpan' / 'config'
        config_dir.mkdir(parents=True, exist_ok=True)
        img_path = config_dir / 'qr_code.png'

        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(url)
        qr.make(fit=True)
        qr.make_image(fill_color='black', back_color='white').save(str(img_path))

        print(f"✅ 二维码已生成: {img_path}")
        _open_image(str(img_path))
    except Exception as e:
        logger.warning(f"生成二维码图片失败: {e}")

    # 终端 ASCII 作为备用
    print_ascii_qr(url)
