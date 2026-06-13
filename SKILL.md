---
name: quarkpan
description: Quark Cloud Drive (夸克网盘) 操作技能。支持扫码登录、文件管理、上传下载、分享转存等。使用 /quarkpan 激活。
metadata:
  tags: quark, cloud-drive, file-management, upload, download, share, python, quarkpan
---

# QuarkPan Skill

夸克网盘 CLI 操作技能。通过 `quarkpan` 命令行工具执行所有网盘操作。

## Activation

当用户提到以下关键词时激活：夸克网盘、quarkpan、网盘、扫码登录、列出文件、搜索、上传、下载、分享、转存

## Installation

**仓库源选择规则**：
- 用户说「用 Gitee / Gitee 安装 / 国内加速 / 国内镜像 / gitee」→ 走 Gitee 命令
- 用户说「用 GitHub / GitHub 安装」→ 走 GitHub 命令
- 用户未指定 → 默认 GitHub

一键安装（克隆代码 + pip安装 + 部署skill）：

```bash
# GitHub
bash <(curl -sL https://raw.githubusercontent.com/woshihoujinxin/quarkpan-skill/main/install.sh)
# Gitee
bash <(curl -sL https://gitee.com/houjinxin/quarkpan-skill/raw/main/install.sh)
```

如需在 GitHub 安装脚本下强制走 Gitee 仓库（适合 Gitee 命令被 GFW 阻断时的兜底），可用 `QUARKPAN_REPO_URL` 覆盖：

```bash
QUARKPAN_REPO_URL=https://gitee.com/houjinxin/quarkpan-skill.git bash <(curl -sL https://raw.githubusercontent.com/woshihoujinxin/quarkpan-skill/main/install.sh)
```

或手动安装：

```bash
# GitHub
git clone https://github.com/woshihoujinxin/quarkpan-skill.git ~/.quarkpan-skill
# Gitee
# git clone https://gitee.com/houjinxin/quarkpan-skill.git ~/.quarkpan-skill

cd ~/.quarkpan-skill && pip install . --quiet
mkdir -p ~/.claude/skills/quarkpan && cp SKILL.md ~/.claude/skills/quarkpan/
```

首次使用需要扫码登录（见下方）。

### 扫码登录流程

登录需要两步操作（因为终端二维码显示有时效问题）：

**步骤1** — 生成二维码图片并打开：
```bash
python -c "
import sys, os; sys.stdout.reconfigure(encoding='utf-8')
from quark_client.auth.api_login import APILogin
from quark_client.auth import QuarkAuth
import qrcode

login = APILogin(timeout=300)
qr_token, qr_url = login.get_qr_code()
with open('config/qr_token.txt', 'w') as f: f.write(qr_token)

os.makedirs('config', exist_ok=True)
qr = qrcode.QRCode(box_size=10, border=4)
qr.add_data(qr_url); qr.make(fit=True)
qr.make_image(fill_color='black', back_color='white').save('config/qr_code.png')
print(f'QR Token saved. URL: {qr_url}')
" && start config/qr_code.png
```

**步骤2** — 用户扫码后，轮询确认登录：
```bash
python -c "
import sys, json, time; sys.stdout.reconfigure(encoding='utf-8')
from quark_client.auth.api_login import APILogin
from quark_client.auth import QuarkAuth

with open('config/qr_token.txt') as f: qr_token = f.read().strip()
login = APILogin(timeout=30)

for i in range(15):
    result = login.check_login_status(qr_token)
    if result is not None:
        if login._is_login_success(result):
            login._process_login_result(result)
            cookies = [f'{c.name}={c.value}' for c in login.client.cookies.jar if c.domain and 'quark.cn' in c.domain]
            QuarkAuth()._save_cookies(QuarkAuth()._parse_cookie_string('; '.join(cookies)))
            print(f'LOGIN_SUCCESS ({len(cookies)} cookies)'); break
        elif login._is_login_failed(result):
            print('LOGIN_FAILED'); break
    time.sleep(1)
else:
    print('LOGIN_TIMEOUT')
"
```

## CLI Commands

### 认证

| 命令 | 用途 |
|------|------|
| `quarkpan auth login` | 扫码登录 |
| `quarkpan auth login --method simple` | 手动 Cookie 登录 |
| `quarkpan auth status` | 查看登录状态 |
| `quarkpan auth logout` | 登出 |

### 文件浏览

| 命令 | 用途 |
|------|------|
| `quarkpan ls` | 列出根目录文件 |
| `quarkpan ls "文件夹名"` | 按名称/路径列出（如 `网盘拉新/子目录`） |
| `quarkpan ls <folder_id>` | 按 ID 列出指定文件夹 |
| `quarkpan ls --fid` | 显示文件/文件夹 ID（用于 rm、share 等需要 ID 的操作） |
| `quarkpan ls --details` | 详细列表（含大小、时间） |
| `quarkpan ls --page 2 --size 50` | 分页 |
| `quarkpan ls --folders-only` | 只看文件夹 |
| `quarkpan ls --files-only` | 只看文件 |
| `quarkpan browse` | 交互式浏览 |
| `quarkpan fileinfo <file_id>` | 文件详细信息 |

### 搜索

| 命令 | 用途 |
|------|------|
| `quarkpan search "关键词"` | 全盘搜索 |
| `quarkpan search --ext pdf "关键词"` | 按扩展名搜索 |
| `quarkpan search --details "关键词"` | 详细结果 |
| `quarkpan search --min-size 1MB "关键词"` | 按大小过滤 |

### 文件操作

| 命令 | 用途 |
|------|------|
| `quarkpan mkdir "名称"` | 创建文件夹 |
| `quarkpan mkdir "名称" --parent <id>` | 在指定目录创建（`--parent` 必须用 ID） |
| `quarkpan rm "路径"` | 按路径删除 |
| `quarkpan rm --id --force <fid1> <fid2>` | 按 ID 强制删除（ID 从 `ls --fid` 获取） |
| `quarkpan rename "路径" "新名"` | 重命名 |
| `quarkpan upload "文件路径"` | 上传到根目录 |
| `quarkpan upload "文件" --parent <id>` | 上传到指定目录（`--parent` 必须用 ID） |
| `quarkpan move "路径" --to "目标"` | 移动文件 |

### 下载

| 命令 | 用途 |
|------|------|
| `quarkpan download file <file_id>` | 下载文件 |
| `quarkpan download file <id> --output "路径"` | 指定保存路径 |
| `quarkpan download files <id1> <id2>` | 批量下载 |
| `quarkpan download folder <folder_id>` | 下载文件夹 |

### 分享

| 命令 | 用途 |
|------|------|
| `quarkpan share "<fid>" --use-id --title "标题"` | 用 ID 创建分享（推荐） |
| `quarkpan share "路径" --title "标题"` | 用路径创建分享 |
| `quarkpan share "路径" --password 1234` | 带密码分享 |
| `quarkpan share "路径" --expire 7` | 7天有效期 |
| `quarkpan shares` | 我的分享列表 |
| `quarkpan save "分享链接"` | 转存分享 |
| `quarkpan save "链接" --folder "/目标/"` | 转存到指定目录 |
| `quarkpan batch-save "链接1" "链接2"` | 批量转存 |
| `quarkpan batch-share` | 批量分享目录 |
| `quarkpan batch-share --target-dir "/路径"` | 指定目录批量分享 |

### 状态

| 命令 | 用途 |
|------|------|
| `quarkpan status` | 登录状态 + 文件统计 |
| `quarkpan list-dirs` | 查看目录结构 |
| `quarkpan version` | 版本信息 |

## Key Concepts

- **folder_id `"0"`** = 根目录
- **file_type `0"`** = 文件夹
- **Cookies 存储路径**（按优先级命中即返回）：
  1. `QUARK_COOKIES_FILE` 环境变量（绝对优先）
  2. `QUARK_CONFIG_DIR` 环境变量目录下的 `cookies.json`
  3. **`~/.config/quarkpan/cookies.json`**（多端共享约定，所有平台一致：Linux/macOS/Windows）
  4. `~/.openclaw/workspace/skills/quarkpan/cookies.json`（OpenClaw 形态探测，无需环境变量）
  5. `~/.claude/skills/quarkpan/cookies.json`（Claude 技能目录）
  6. `~/.quarkpan/config/cookies.json`（向后兼容 fallback）
- **多端同步**：把 `~/.config/quarkpan/` 用 syncthing / iCloud / OneDrive 同步到其他机器，所有机器共享同一份登录态，无需每端扫码。
- 分享链接格式：`https://pan.quark.cn/s/{share_id}`
- 仓库地址：
  - GitHub：`https://github.com/woshihoujinxin/quarkpan-skill`
  - Gitee：`https://gitee.com/houjinxin/quarkpan-skill`
