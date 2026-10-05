"""纯标准库 PNG 写出（只用 zlib + struct，不依赖 Pillow / pypng / 任何第三方库）。

为什么手写：二维码是 1bit 黑白图，用 PNG 规范直写只需几十行。而第三方路线各有代价 ——
Pillow 是平台绑定的二进制 wheel（离线包刻意不含，见 pyproject 中移除 pydantic 的注释），
qrcode 的 `image.pure.PyPNGImage` 又额外要求 pypng。手写后：

* **零新增依赖**：离线包（`deps/wheels/`，全部 py3-none-any）不用再加任何 wheel；
* **恒定出 PNG**：不再有「装了 Pillow 才出 PNG，否则回落 SVG」的分支，
  也就不会出现「同一份文档，有人拿到 PNG、有人拿到 SVG」这种要靠转换补的情况。

历史教训（2026-10-05）：原实现优先 PNG（需 Pillow）→ 失败回落 SVG，而离线环境没有
Pillow，于是实际总是产出 SVG，Agent 还得再想办法把 SVG 转成能在对话里直接展示的位图，
白白多花一轮。现定死 PNG。
"""

import struct
import zlib
from typing import List, Tuple

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunk(tag: bytes, payload: bytes) -> bytes:
    """打包一个 PNG chunk：长度 + 类型 + 数据 + CRC32。"""
    return (
        struct.pack(">I", len(payload))
        + tag
        + payload
        + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
    )


def write_gray_png(path: str, width: int, height: int, pixels: bytes) -> None:
    """把 8bit 灰度像素写成 PNG（color type 0）。

    pixels：行优先、每像素 1 字节（0=黑，255=白），长度必须是 width*height。
    """
    stride = width
    if len(pixels) != stride * height:
        raise ValueError(f"像素数据长度不符：期望 {stride * height}，实际 {len(pixels)}")

    raw = bytearray()
    for y in range(height):
        raw.append(0)  # 每行前缀一个滤波类型字节：0 = None
        raw += pixels[y * stride : (y + 1) * stride]

    ihdr = struct.pack(
        ">IIBBBBB",
        width,
        height,
        8,  # bit depth
        0,  # color type：0 = 灰度
        0,  # compression
        0,  # filter
        0,  # interlace
    )
    data = (
        _PNG_SIGNATURE
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )
    with open(path, "wb") as fh:
        fh.write(data)


def write_matrix_png(
    path: str,
    matrix: List[List[bool]],
    box_size: int = 10,
    dark: int = 0,
    light: int = 255,
) -> str:
    """把二维码模块矩阵渲染成 PNG（每个模块 box_size x box_size 像素）。

    `matrix` 直接用 `qrcode.QRCode.get_matrix()` 的返回值（已含 border）。
    返回写出的绝对/相对路径字符串。
    """
    rows = len(matrix)
    cols = len(matrix[0]) if rows else 0
    width = cols * box_size
    height = rows * box_size
    pixels = bytearray(width * height)

    for ry, row in enumerate(matrix):
        y0 = ry * box_size
        for cx, on in enumerate(row):
            color = dark if on else light
            x0 = cx * box_size
            for y in range(y0, y0 + box_size):
                base = y * width
                pixels[base + x0 : base + x0 + box_size] = bytes([color]) * box_size

    write_gray_png(path, width, height, bytes(pixels))
    return path


def write_qr_png(path: str, data: str, box_size: int = 10, border: int = 4) -> str:
    """编码 `data` 并写成 PNG。失败抛异常（不静默回落成别的格式）。"""
    import qrcode

    qr = qrcode.QRCode(box_size=box_size, border=border)
    qr.add_data(data)
    qr.make(fit=True)
    return write_matrix_png(path, qr.get_matrix(), box_size=box_size)


def read_gray_png(path: str) -> Tuple[int, int, bytes]:
    """读回自己写出的 PNG（仅供测试/自检用），返回 (width, height, pixels: bytes)。"""
    with open(path, "rb") as fh:
        blob = fh.read()
    if blob[:8] != _PNG_SIGNATURE:
        raise ValueError("不是 PNG 文件")
    pos = 8
    width = height = 0
    idat = b""
    while pos < len(blob):
        (length,) = struct.unpack(">I", blob[pos : pos + 4])
        tag = blob[pos + 4 : pos + 8]
        payload = blob[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if tag == b"IHDR":
            width, height, depth, ctype = struct.unpack(">IIBB", payload[:10])
            if depth != 8 or ctype != 0:
                raise ValueError(f"仅支持 8bit 灰度，实际 depth={depth} ctype={ctype}")
        elif tag == b"IDAT":
            idat += payload
        elif tag == b"IEND":
            break
    raw = zlib.decompress(idat)
    stride = width
    out = bytearray()
    for y in range(height):
        start = y * (stride + 1)
        if raw[start] != 0:
            raise ValueError("仅支持滤波类型 0")
        out += raw[start + 1 : start + 1 + stride]
    return width, height, bytes(out)


def is_valid_png(path: str) -> bool:
    """轻量校验：签名正确且能被自己解回来。"""
    try:
        read_gray_png(path)
        return True
    except Exception:
        return False
