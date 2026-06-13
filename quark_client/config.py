"""
配置管理模块
"""

import os
from pathlib import Path
from typing import Any, Dict

from .utils.logger import get_logger


def _user_config_dir() -> Path:
    """统一用户配置目录：``~/.config/quarkpan``。

    所有平台一致，不区分 XDG / Windows。Git Bash / WSL 也走这条路径。
    """
    return Path.home() / '.config' / 'quarkpan'


def get_config_dir() -> Path:
    """获取配置目录路径。

    解析顺序：
    1. 环境变量 ``QUARK_CONFIG_DIR`` 显式指定
    2. ``~/.config/quarkpan``（统一约定，多端一致）
    3. 旧 fallback ``~/.quarkpan/config``（向后兼容）
    """
    config_dir = os.getenv('QUARK_CONFIG_DIR')
    if config_dir:
        return Path(config_dir).expanduser()

    user_dir = _user_config_dir()
    if user_dir.is_dir():
        return user_dir

    legacy = Path.home() / '.quarkpan' / 'config'
    legacy.mkdir(parents=True, exist_ok=True)
    return legacy


def _detect_skill_root() -> Path | None:
    """
    探测当前 skill 包的安装根目录。

    通过 __file__ 向上寻找，直到包含 SKILL.md 的目录，识别为技能根目录。
    若找不到则返回 None。
    """
    try:
        here = Path(__file__).resolve()
    except NameError:
        return None

    for parent in here.parents:
        if (parent / "SKILL.md").is_file():
            return parent
        # 兼容源码包被直接 import 时没有 SKILL.md 的情况
        if parent.name == "quarkpan" and (parent.parent / "SKILL.md").is_file():
            return parent.parent
    return None


def get_cookies_file() -> Path:
    """
    获取 cookies.json 的存储路径。

    解析顺序（命中即返回，后面的不再检查）：
    1. 环境变量 ``QUARK_COOKIES_FILE`` 显式指定文件
    2. 环境变量 ``QUARK_CONFIG_DIR`` 指定目录下的 cookies.json
    3. ``~/.config/quarkpan/cookies.json`` 已存在（多端共享约定，优先于单技能形态探测）
    4. ``~/.openclaw/workspace/skills/quarkpan/cookies.json``（OpenClaw 形态探测）
    5. ``__file__`` 推断出的技能根（如果是 OpenClaw 形态）
    6. ``~/.claude/skills/quarkpan/cookies.json``（Claude 形态探测）
    7. ``__file__`` 推断出的技能根（如果是 Claude 形态）
    8. 默认归宿：``~/.config/quarkpan/cookies.json``（多端共享，便于发现和迁移）
    9. 旧 fallback ``~/.quarkpan/config/cookies.json``（向后兼容）

    父目录会被自动创建。
    """
    logger = get_logger(__name__)

    # 1) 显式指定文件
    explicit = os.getenv('QUARK_COOKIES_FILE')
    if explicit:
        path = Path(explicit).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"cookies 路径 (QUARK_COOKIES_FILE): {path}")
        return path

    # 2) 指定配置目录
    config_dir_env = os.getenv('QUARK_CONFIG_DIR')
    if config_dir_env:
        path = Path(config_dir_env).expanduser() / 'cookies.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"cookies 路径 (QUARK_CONFIG_DIR): {path}")
        return path

    user_cookies = _user_config_dir() / 'cookies.json'

    # 3) ~/.config/quarkpan/cookies.json 已存在 → 优先用（多端共享）
    if user_cookies.is_file():
        logger.debug(f"cookies 路径 (user_config, existing): {user_cookies}")
        return user_cookies

    skill_root = _detect_skill_root()

    # 4) OpenClaw 形态探测：~/.openclaw/workspace/skills/quarkpan/SKILL.md 是否存在
    openclaw_skill_dir = Path.home() / '.openclaw' / 'workspace' / 'skills' / 'quarkpan'
    if (openclaw_skill_dir / 'SKILL.md').is_file():
        path = openclaw_skill_dir / 'cookies.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"cookies 路径 (openclaw skill): {path}")
        return path

    # 5) __file__ 落在 OpenClaw 形态（pip install 到 OpenClaw workspace 的情况）
    if skill_root is not None and _is_openclaw_skill_root(skill_root):
        path = skill_root / 'cookies.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"cookies 路径 (openclaw skill, by __file__): {path}")
        return path

    # 6) Claude 形态探测：~/.claude/skills/quarkpan/SKILL.md 是否存在
    claude_skill_dir = Path.home() / '.claude' / 'skills' / 'quarkpan'
    if (claude_skill_dir / 'SKILL.md').is_file():
        path = claude_skill_dir / 'cookies.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"cookies 路径 (claude skill): {path}")
        return path

    # 7) __file__ 落在 Claude 形态
    if skill_root is not None and _is_claude_skill_root(skill_root):
        path = skill_root / 'cookies.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"cookies 路径 (claude skill, by __file__): {path}")
        return path

    # 8) 默认归宿：~/.config/quarkpan/（多端共享，便于发现和迁移）
    user_cookies.parent.mkdir(parents=True, exist_ok=True)
    logger.debug(f"cookies 路径 (user_config, default for new install): {user_cookies}")
    return user_cookies

    # 9) 旧 fallback（向后兼容）
    legacy_path = Path.home() / '.quarkpan' / 'config' / 'cookies.json'
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    logger.debug(f"cookies 路径 (legacy default): {legacy_path}")
    return legacy_path


def _is_openclaw_skill_root(skill_root: Path) -> bool:
    """技能根目录是否落在 OpenClaw 的 ``workspace/skills/quarkpan`` 形态下。"""
    parts = skill_root.parts
    return len(parts) >= 3 and parts[-1] == 'quarkpan' \
        and parts[-2] == 'skills' and parts[-3] == 'workspace'


def _is_claude_skill_root(skill_root: Path) -> bool:
    """技能根目录是否落在 Claude 的 ``.claude/skills/quarkpan`` 形态下。"""
    parts = skill_root.parts
    return len(parts) >= 3 and parts[-1] == 'quarkpan' \
        and parts[-2] == 'skills' \
        and (parts[-3] in ('.claude', 'claude'))


def get_default_headers() -> Dict[str, str]:
    """获取默认的HTTP请求头"""
    return {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko)'
                      ' Chrome/94.0.4606.71 Safari/537.36 Core/1.94.225.400 QQBrowser/12.2.5544.400',
        'origin': 'https://pan.quark.cn',
        'referer': 'https://pan.quark.cn/',
        'accept-language': 'zh-CN,zh;q=0.9',
        'accept': 'application/json, text/plain, */*',
        'content-type': 'application/json',
    }


class Config:
    """配置类"""

    # API相关配置
    BASE_URL = 'https://drive-pc.quark.cn/1/clouddrive'
    SHARE_BASE_URL = 'https://drive.quark.cn/1/clouddrive'
    ACCOUNT_URL = 'https://pan.quark.cn/account'

    # 默认参数
    DEFAULT_PARAMS = {
        'pr': 'ucpro',
        'fr': 'pc',
        'uc_param_str': '',
    }

    # 请求超时设置
    REQUEST_TIMEOUT = 60.0

    # 重试设置
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0

    # 分页设置
    DEFAULT_PAGE_SIZE = 50
    MAX_PAGE_SIZE = 100

    # 文件下载设置
    DOWNLOAD_CHUNK_SIZE = 8192
    DOWNLOAD_DIR = 'downloads'
