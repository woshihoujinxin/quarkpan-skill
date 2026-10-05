#!/bin/bash
# QuarkPan Skill 一键安装脚本
# 用法:
#   GitHub: bash <(curl -sL https://raw.githubusercontent.com/woshihoujinxin/quarkpan-skill/main/install.sh)
#   Gitee:  bash <(curl -sL https://gitee.com/houjinxin/quarkpan-skill/raw/main/install.sh)

set -e

# ⚠️ 本脚本用于「单独安装 QuarkPan 技能」：clone 本仓库 + pip install + 部署 SKILL.md。
#
# 🚫 如果你是**通过闲鱼分发包（xianyu-pipeline）**拿到本 SDK 的，请不要运行本脚本。
#    分发包已内置离线 wheel 与全部依赖，正确做法是在解压目录执行：
#        pip install --no-index --find-links ./deps/wheels quarkpan-ks
#    走本脚本会 clone 网络仓库、装到与分发包不一致的版本，属于自找麻烦。
#
# 另注：本脚本曾执行 `pip install .`，其发行名历史上叫 quarkpan（与 PyPI 官方包撞名）；
# 现已改名为 quarkpan-ks，install 不会再误装官方版。

SKILL_DIR="$HOME/.claude/skills/quarkpan"
REPO_DIR="$HOME/.quarkpan-skill"
REPO_URL="${QUARKPAN_REPO_URL:-https://github.com/woshihoujinxin/quarkpan-skill.git}"

echo "=== QuarkPan Skill Installer ==="

# Clone repo
echo "Cloning repo..."
git clone "$REPO_URL" "$REPO_DIR"

# Install package (non-editable, so source can be deleted after)
echo "Installing quarkpan..."
cd "$REPO_DIR"
pip install . --quiet

# Deploy skill file
echo "Deploying skill..."
mkdir -p "$SKILL_DIR"
cp "$REPO_DIR/SKILL.md" "$SKILL_DIR/SKILL.md"

# Clean up source code
echo "Cleaning up source..."
rm -rf "$REPO_DIR"

echo ""
echo "=== Install Complete ==="
echo "Skill:    ~/.claude/skills/quarkpan/SKILL.md"
echo "Config:   ~/.quarkpan/config/  (cookies, login data)"
echo "Commands: /quarkpan to activate"
echo ""
echo "First time? Run the login flow described in the skill."
