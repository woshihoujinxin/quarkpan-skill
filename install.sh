#!/bin/bash
# QuarkPan Skill 一键安装脚本
# 用法: bash <(curl -sL https://raw.githubusercontent.com/woshihoujinxin/quarkpan-skill/main/install.sh)

set -e

SKILL_DIR="$HOME/.claude/skills/quarkpan"
REPO_DIR="$HOME/.quarkpan-skill"
REPO_URL="https://github.com/woshihoujinxin/quarkpan-skill.git"

echo "=== QuarkPan Skill Installer ==="

# Clone or update repo
if [ -d "$REPO_DIR" ]; then
    echo "Updating existing repo..."
    cd "$REPO_DIR" && git pull
else
    echo "Cloning repo..."
    git clone "$REPO_URL" "$REPO_DIR"
fi

# Install package
echo "Installing quarkpan..."
cd "$REPO_DIR"
pip install -e .

# Deploy skill file
echo "Deploying skill..."
mkdir -p "$SKILL_DIR"
cp "$REPO_DIR/SKILL.md" "$SKILL_DIR/SKILL.md"

echo ""
echo "=== Install Complete ==="
echo "Skill:    ~/.claude/skills/quarkpan/SKILL.md"
echo "Repo:     $REPO_DIR"
echo "Commands: /quarkpan to activate"
echo ""
echo "First time? Run 'quarkpan auth login' to login."
