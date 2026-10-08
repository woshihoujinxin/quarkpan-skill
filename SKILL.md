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

### 方式一 · 随分发包安装（最终用户**只能用这个**）

组合分发包里已内置 SDK wheel 和全部依赖，**无需联网、无需 clone 源码**：

```bash
# PACKAGE_DIR = 解压后的分发包目录，如 xianyu-pipeline-1.0.0
pip install --no-index --find-links "$PACKAGE_DIR/deps/wheels" quarkpan-ks
```

> 🔴 三条硬规则（违反会导致登录失败）：
> 1. **必须带 `--no-index`**。PyPI 上有一个**同名不同源**的官方包 `quarkpan`，联网解析
>    可能装到它 —— 那版缺 `get_cookies_file` 等本地改动，后续登录必然失败。
> 2. 发行名是 **`quarkpan-ks`**（不是 `quarkpan`）。**不要**执行 `pip install quarkpan`。
> 3. **不要** `pip install --upgrade quarkpan` —— 那是把本地维护版降级成官方旧版。
>
> 装完 `quarkpan version` 应显示 **v1.0.7**；显示其它版本说明装错了包。

### 方式二 · 从源码仓库安装（⚠️ 仅维护者自测用，最终用户请勿走）

> 🚫 最终用户**不要**用这条路。clone + 重装会绕过包内锁定的依赖版本，
> 也可能装到与分发包不一致的代码。它只用于维护者改完 SDK 后本地自测。

```bash
git clone https://github.com/woshihoujinxin/quarkpan-skill.git ~/.quarkpan-skill
cd ~/.quarkpan-skill && pip install -e .
# 拷 SKILL.md 到「你自己的 Agent」技能目录（路径随 Agent 而变，勿写死）
mkdir -p "${SKILLS_DIR:-$HOME/.workbuddy/skills}/quarkpan" \
  && cp SKILL.md "${SKILLS_DIR:-$HOME/.workbuddy/skills}/quarkpan/"
```

安装后均提供 `quarkpan` 命令，验证：

```bash
quarkpan version
```

首次使用需要扫码登录（见下方）。

### 🚑 装完却用不了？先看这里（AI 别走弯路）

这类问题**不是没装**，照着下表直接执行，不要从零排查（每个都要白跑十几步）：

| 症状 | 真实根因 | 直接执行 |
|---|---|---|
| `quarkpan: command not found` | 它装在**某个 Python 的 bin 目录**里，不在 PATH（≠ 没装） | 走流水线 `${SKILL_DIR}/../auto-list/scripts/run.py`（内置绝对路径解析）；必须手敲时先 `python3 -m pip show -f quarkpan-ks` 看 `Location`，用绝对路径 |
| 报「未登录」但 `~/.config/quarkpan/cookies.json` **存在** | 装的是**旧版 wheel**，旧版有误报 bug（**不是**登录态丢了） | `python3 -m pip install --force-reinstall --no-deps "$PACKAGE_DIR/deps/wheels/quarkpan_ks-1.0.7-py3-none-any.whl"` |
| `quarkpan version` 不是 **v1.0.7** | 装到 PyPI 上的**同名官方包**了 | 同上，用 wheel 强制重装 |
| `curl https://pan.quark.cn/...` 报 TLS 错（exit 35） | 该站不吃 curl 的默认握手 | 改用 Python `httpx`（流水线内已这么做） |

> 🔴 **硬规则**：报「未登录」时**先 `quarkpan version` 查版本**。版本不对 ⇒ 直接重装 wheel；
> **不要**先去重新扫码 —— 旧版 wheel 的误报 bug 会让你反复白扫、还以为是码过期。

### 🔧 已知坑与**修复状态**（2026-10-05 实测）

> **写文档的硬规矩**：报坑必须同时写「状态 + 修复版本 + 老版本怎么办」。
> 只写坑不写状态，下一个 AI 会把它当**待办**重新排一遍 —— 每次都白跑十几步。
> 下表每一条都是**真机实测**（含修复前的复现与修复后的复测），不是推断。

| # | 症状（AI 看到的原文） | 真实根因（**不是**你以为的那个） | 状态 | 老版本（< 1.0.7）怎么办 |
|---|---|---|---|---|
| 1 | `quarkpan rm …` **卡住不动**，最后 exit **137**、零输出；或 `rm` 报 `删除文件失败: EOF when reading a line` | 不带 `-f` 会走交互确认，而**非交互 shell 没有 TTY**：stdin 是「已打开但永不写入」的管道 ⇒ 永久阻塞直到被 SIGTERM。（**不是**网络卡住、**不是**文件被占用、**不是**没登录） | ✅ **已修复**（quarkpan-ks ≥ **1.0.7**）：非交互且未给 `-f` → **秒级**退出码 **2** 并提示加 `-f`，且**绝不误删** | 一律显式加 `-f`：`quarkpan rm -f --id <fid>` |
| 2 | `rm` / `rename` 的预览打印出**别的文件**（删一个 zip，却显示 `文件夹: workbuddy-闲鱼自动化`），看着像要删整个文件夹 | 旧详情接口是 `GET file?fids=`，该端点只认 `pdir_fid`（列目录语义），`fids` 被服务端**静默忽略**并回落成「根目录列表」，再被「没匹配到就 `return file_list[0]`」的兜底吞掉 ⇒ 返回**根目录第一条**。（**实际删除只作用于你给的那个 fid**，文件夹没被碰） | ✅ **已修复**（≥ 1.0.7）：改用 `GET file/info?fid=<fid>`，并**删掉**「返回第一条」兜底（拿不准就报错） | 别信预览文案：判据一律是操作前后 `ls --fid` 的**条目数 / ID 差集** |
| 3 | `quarkpan fileinfo <fid>` 报 `unable to render int; a string or other renderable object is required` | `created_at` / `updated_at` 是 **int 时间戳**，直接塞进 rich `Table` 渲染不了（该命令此前没人跑，这个坑一直没暴露） | ✅ **已修复**（≥ 1.0.7） | 用 `quarkpan ls <dir> --fid` 看名字，别用 `fileinfo` |
| 4 | `quarkpan` 报「未登录」但 cookies 文件在 | 装的是**旧版 wheel**（旧版有误报 bug），**不是**登录态丢了 | 早于 1.0.7 的版本**务必重装** | `python3 -m pip install --force-reinstall --no-deps "$PACKAGE_DIR/deps/wheels/quarkpan_ks-1.0.7-py3-none-any.whl"` |

**升级到修复版（离线可用，一条命令）**：

```bash
PACKAGE_DIR="<解压后的分发包目录>"       # 例如 xianyu-pipeline-1.0.0
python3 -m pip install --no-index --find-links "$PACKAGE_DIR/deps/wheels" \
  --force-reinstall --no-deps quarkpan-ks
quarkpan version                          # 期望输出 QuarkPan CLI v1.0.7
```

> 🔴 **为什么必须写「状态」**：坑 1、坑 2 的**表象全是误导**（一个像网络卡住，一个像要删整个文件夹）。
> 不写状态，后续 AI 会先去怀疑网络 / 权限 / token，然后重装、重新扫码 —— 全是错方向，白跑一轮。
> 坑 1 的**回归测试**与**真机复测**见 `deps/quarkpan-skill/tests/test_rm_and_info_contract.py`（20 例）。

### 扫码登录流程

两步：**先出码**（不阻塞）→ 用户扫码 → **再等扫码**（这一步才会落盘 cookies）。

> 🔴 **用 CLI 内建能力，不要自己 `import qrcode` 画图。**
> `quarkpan auth qr` / `quarkpan auth wait` 就是为「Agent 需要先把图片交给用户、
> 之后才能等扫码」这个场景提供的；自己手搓只能得到一份和 SDK 不同步的实现。

**步骤1** — 出码（立刻返回，不阻塞）：
```bash
quarkpan auth qr --no-open
```
输出（机器可读，直接取用）：
```
QR_PNG_PATH=/…/.config/quarkpan/qr_code.png   ← 把这个 PNG 发给用户（Agent 用附图能力展示）
QR_TOKEN=sta32…
```
> 🔴 **格式定死 PNG，没有 SVG 分支。** PNG 由 SDK 内置 `quark_client/utils/qr_png.py`
> 用**纯标准库（zlib + struct）直写**：不依赖 Pillow、不依赖 pypng，离线包不用多任何 wheel。
> 历史上「PNG 需 Pillow → 失败回落 SVG」的做法会让离线环境总产 SVG，Agent 还得再想办法
> 把 SVG 转成位图，白白多花一轮 —— 别再走回头路。

**步骤2** — 用户扫码后，等确认（**这一步才会落盘 cookies.json**）：
```bash
quarkpan auth wait
```
看到 `LOGIN_SUCCESS` 即完成。

> 🔴 **不要**用 `check_login_status` 自己写轮询循环，也**不要**调 `_save_login_result`
> —— 后者在当前版本**根本不存在**（旧文档遗留，照抄会 `AttributeError`）；前者只查状态
> 不落盘。`quarkpan auth wait` 内部走的 `wait_for_login` 是唯一会**把登录凭证写入
> `~/.config/quarkpan/cookies.json`** 的入口。不落盘 ⇒ `quarkpan auth status` 永远报未登录。
>
> `quarkpan auth login` 也能用（一步到底），但它会**阻塞**到扫码完成，
> 中途没法把二维码先交给用户，因此 Agent 场景优先用 `auth qr` + `auth wait`。

验证：

```bash
quarkpan auth status     # 预期输出「已登录」
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
| `quarkpan fileinfo <fid>` | 按 fid 看单个文件详情（v1.0.7 起可用） |

> 🔴 **删/改必须带 `-f`**：脚本与 Agent 一律写 `quarkpan rm -f --id <fid>`。
> 不带 `-f` 会去问确认，而**非交互 shell 没有 TTY** —— v1.0.6 及以前会**永久挂死**
> （exit 137、零输出）；v1.0.7 起会**秒级**退出码 2 并提示加 `-f`（不会误删）。详见上方「已知坑与修复状态」坑 1。
>
> 🔴 **别拿预览文案当判据**：v1.0.6 及以前，`rm` / `rename` 的预览会显示成**别的文件**（坑 2）。
> 判断「到底动了哪个文件」一律看操作前后 `quarkpan ls <目录> --fid` 的**条目数 / ID 差集**。

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

#### ⚠️ 排查「大文件下载失败」时不要走弯路（已确认结论）

| 错误方向 | 实际结论 |
|---|---|
| 查会员是否到期 | ❌ 无关。实测 23018 与 `member_status` / `subscribe_freeze_type_map` 无因果 |
| 怀疑 CLI 传参错误 | ❌ 无关。10 组参数矩阵（pr/fr/sys/ve/域名）全灭，同参数下 47.5MB 过、50.3MB 拒 |
| 换端点 drive-m / pan | ❌ 无关，三域名结果一致 |
| 分享通道绕过 | ❌ PC API 上 `share/sharepage/download` 等均 404 |
| **换桌面客户端 UA** | ✅ **唯一有效**，且拿到的是**原文件**（size 字节级一致） |

**踩坑**：`get_default_headers()` 返回的键是**小写 `user-agent`**，直接 `headers['User-Agent'] = ...`
会因 httpx 规范化「小写键先到先得」而**被默认 UA 覆盖**，必须先删掉所有 `user-agent` 键再设。

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
- Cookies 存储在 `config/cookies.json`
- 分享链接格式：`https://pan.quark.cn/s/{share_id}`
- 源码仓库：`https://github.com/woshihoujinxin/quarkpan-skill`
- 分发包内位置：`deps/quarkpan-skill/`（见 `THIRD-PARTY-LICENSES.md`）
