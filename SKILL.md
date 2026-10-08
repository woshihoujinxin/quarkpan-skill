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
# 拷 SKILL.md 到「你自己的 Agent」技能目录（路径随 Agent 而变，勿写死）：
#   WorkBuddy=~/.workbuddy/skills  Claude=~/.claude/skills  Cursor=~/.cursor/skills …
mkdir -p "${SKILLS_DIR:-$HOME/.workbuddy/skills}/quarkpan" \
  && cp SKILL.md "${SKILLS_DIR:-$HOME/.workbuddy/skills}/quarkpan/"
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
| `quarkpan fileinfo <fid>` | 按 fid 看单个文件详情（v1.0.8 起可用） |

> 🔴 **删/改必须带 `-f`**：脚本与 Agent 一律写 `quarkpan rm -f --id <fid>`。不带 `-f` 会去问确认，
> 而**非交互 shell 没有 TTY** —— v1.0.6 及以前会**永久挂死**（exit 137、零输出）；v1.0.8 起**秒级**退出码 2 并提示加 `-f`。

### 🔧 已知坑与**修复状态**（2026-10-05 实测）

> **写文档的硬规矩**：报坑必须同时写「状态 + 修复版本 + 老版本怎么办」。
> 只写坑不写状态，下一个 AI 会把它当**待办**重新排一遍 —— 每次都白跑十几步。
> 下表每条都是**真机实测**（修复前复现 + 修复后复测），不是推断。

| # | 症状（AI 看到的原文） | 真实根因（**不是**你以为的那个） | 状态 | 老版本（< 1.0.8）怎么办 |
|---|---|---|---|---|
| 1 | `quarkpan rm …` **卡住不动**，最后 exit **137**、零输出；或 `rm` 报 `删除文件失败: EOF when reading a line` | 不带 `-f` 会走交互确认，而**非交互 shell 没有 TTY**：stdin 是「已打开但永不写入」的管道 ⇒ 永久阻塞直到被 SIGTERM。（**不是**网络卡住、**不是**文件被占用、**不是**没登录） | ✅ **已修复**（≥ **1.0.8**）：非交互且未给 `-f` → **秒级**退出码 **2** 并提示加 `-f`，**绝不误删** | 一律显式加 `-f` |
| 2 | `rm` / `rename` 预览打印出**别的文件**（删一个 zip，却显示 `文件夹: workbuddy-闲鱼自动化`），看着像要删整个文件夹 | 旧详情接口 `GET file?fids=` 只认 `pdir_fid`（列目录语义），`fids` 被服务端**静默忽略**并回落成「根目录列表」，再被「没匹配到就 `return file_list[0]`」的兜底吞掉 ⇒ 返回**根目录第一条**。（**实际只删你给的 fid**，文件夹没被碰） | ✅ **已修复**（≥ 1.0.8）：改用 `GET file/info?fid=<fid>`，并**删掉**「返回第一条」兜底 | 别信预览：判据是操作前后 `ls --fid` 的**条目数 / ID 差集** |
| 3 | `quarkpan fileinfo <fid>` 报 `unable to render int; a string or other renderable object is required` | `created_at` / `updated_at` 是 **int 时间戳**，rich `Table` 渲染不了（该命令此前没人跑，坑没暴露） | ✅ **已修复**（≥ 1.0.8） | 改用 `quarkpan ls <目录> --fid` |
| 4 | 报「未登录」但 `~/.config/quarkpan/cookies.json` 在 | 装的是**旧版 wheel**（旧版有误报 bug），**不是**登录态丢了 | 早于 1.0.8 的版本**务必重装** | `pip install --force-reinstall --no-deps <quarkpan_ks-1.0.8-py3-none-any.whl>` |

**升级到修复版**：

```bash
python3 -m pip install --force-reinstall --no-deps quarkpan_ks-1.0.8-py3-none-any.whl
quarkpan version        # 期望 QuarkPan CLI v1.0.8
```

> 🔴 **为什么必须写「状态」**：坑 1、坑 2 的**表象全是误导**（一个像网络卡住，一个像要删整个文件夹）。
> 不写状态，后续 AI 会先去怀疑网络 / 权限 / token，然后重装、重新扫码 —— 全是错方向。
> 回归测试：`tests/test_rm_and_info_contract.py`（20 例，含「绝不返回第一条兜底」「非交互不阻塞」两条负向）。

### 下载

| 命令 | 用途 |
|------|------|
| `quarkpan download file <file_id>` | 下载文件 |
| `quarkpan download file <id> --output "路径"` | 指定保存路径 |
| `quarkpan download files <id1> <id2>` | 批量下载 |
| `quarkpan download folder <folder_id>` | 下载文件夹 |

> ✅ **大文件（>50MB）已自动支持**：网页通道对大文件返回 `23018 download file size limit`
> 时，会自动用**桌面客户端标识**（`quark-cloud-drive/2.5.56` UA）重试同一接口，即可拿到
> 可用下载链接。**无需用户手动操作、无需会员、与账号权益无关。**
> 实现见 `quark_client/services/file_download_service.py` 的 `_post_as_desktop()`。
> 参考: https://github.com/zhangjingwei/kuake_cli/pull/37

#### ⚠️ 排查「大文件下载失败」时不要走弯路（2026-10-08 实测结论）

| 错误方向 | 实际结论 |
|---|---|
| 查会员是否到期/冻结 | ❌ 无关。实测账号 `exp_at` 到 2027、冻结已解除，照样报 23018 |
| 怀疑 CLI 传参错误 | ❌ 无关。10 组参数矩阵（pr/fr/sys/ve/域名）全灭；同参数下 47.5MB 过、50.3MB 拒 |
| 换端点 drive-m / pan | ❌ 无关，三域名结果一致 |
| 分享通道绕过 | ❌ PC API 上 `share/sharepage/download` 等均 404 |
| `file/play?resolution=raw` 取原画质直链 | ⚠️ 能用但**较差**：部分文件只给 m3u8，需 ffmpeg 合并且是转码版 |
| **换桌面客户端 UA** | ✅ **正解**，拿到的是**原文件**（size 字节级一致），20/20 全通 |

**踩坑（改代码时必看）**：
- `get_default_headers()` 返回的键是**小写 `user-agent`**。直接
  `headers['User-Agent'] = ...` 会与之**共存**，httpx 规范化时「小写键先到先得」
  ⇒ 桌面 UA 被静默丢弃、仍报 23018。**必须先删掉所有 `user-agent` 键再设**。
- Cookie 挂在 `client.api_client.cookies`，**不在** `client.cookies`；漏了 cookie 同样 23018。

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
