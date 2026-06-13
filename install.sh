#!/bin/bash
# QuarkPan Skill 一键安装脚本
# 用法: bash <(curl -sL https://raw.githubusercontent.com/woshihoujinxin/quarkpan-skill/main/install.sh)

set -e

SKILL_DIR="$HOME/.claude/skills/quarkpan"
REPO_DIR="$HOME/.quarkpan-skill"
REPO_URL="https://github.com/woshihoujinxin/quarkpan-skill.git"

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
