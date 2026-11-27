#!/usr/bin/env bash
# 刷新公开数据页：重建 docs/ 并推送（GitHub Pages 自动发布）。
# 用法：bash scripts/publish_site.sh
# 备注：GitHub Actions 版本见 scripts/github-actions-daily-rank.yml.disabled，
#       因为 gh OAuth token 缺 workflow scope 推不上去；补上 scope 后可直接启用。
set -euo pipefail
cd "$(dirname "$0")/.."

python3 scripts/build_site.py
git add docs
if git diff --cached --quiet; then
  echo "no change"
  exit 0
fi
git -c user.name=xiaomomini -c user.email=xiaomomini@users.noreply.github.com \
    commit -q -m "rank: $(date -u +%Y-%m-%d) snapshot"
git push -q origin HEAD
echo "published $(date -u +%Y-%m-%dT%H:%M:%SZ)"
