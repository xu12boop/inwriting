#!/usr/bin/env bash
# =============================================================================
# InWriting 服务器端一键更新脚本
#
# 用途：在阿里云 ECS 上把 /opt/inwriting 更新到 GitHub main 最新提交，并重启服务。
# 用法：
#     ssh 到你自己的服务器后执行：
#         sudo bash /opt/inwriting/deploy/update.sh
#     或者直接（不进目录）：
#         sudo bash -c 'cd /opt/inwriting && bash deploy/update.sh'
#
# 设计原则：每一步都可单独失败并可回滚；任何一步失败立即停止，不会重启到半成品状态。
# =============================================================================
set -euo pipefail

APP_DIR=/opt/inwriting
RUN_USER=inwriting
SVC=inwriting
HEALTH=http://127.0.0.1:8001/health

cd "$APP_DIR"

echo "==> [1/7] 记录当前版本，便于回滚"
PREV=$(sudo -u "$RUN_USER" git rev-parse --short HEAD || echo unknown)
echo "    当前提交：$PREV"

echo "==> [2/7] 拉取远端最新代码"
# /opt/inwriting 属主是 inwriting，用 root 直接 git pull 会报 dubious ownership，
# 因此统一以 inwriting 身份执行；并显式声明 safe.directory 兜底。
sudo -u "$RUN_USER" git config --global --add safe.directory "$APP_DIR" || true
sudo -u "$RUN_USER" git fetch --prune origin main
sudo -u "$RUN_USER" git reset --hard origin/main
NEW=$(sudo -u "$RUN_USER" git rev-parse --short HEAD)
echo "    更新到：$NEW"

if [ "$PREV" = "$NEW" ]; then
  echo "    代码已是最新，无需继续（如需强制重启，手动执行 systemctl restart $SVC）"
  exit 0
fi

echo "==> [3/7] 同步 Python 依赖（仅在 requirements 变化时执行，避免每次重装）"
if sudo -u "$RUN_USER" git diff --name-only "$PREV" "$NEW" | grep -qE '^requirements.*\.txt$'; then
  echo "    检测到 requirements 变更，安装中…"
  sudo -u "$RUN_USER" "$APP_DIR/venv/bin/pip" install -r requirements.txt
else
  echo "    requirements 未变化，跳过"
fi

echo "==> [4/7] 构建前端（仅在 frontend/ 变化时执行）"
if sudo -u "$RUN_USER" git diff --name-only "$PREV" "$NEW" | grep -qE '^frontend/'; then
  echo "    检测到前端变更，构建中（2G 内存约需 5-30s）…"
  cd "$APP_DIR/frontend"
  sudo -u "$RUN_USER" npm ci --no-audit --no-fund || sudo -u "$RUN_USER" npm install --no-audit --no-fund
  sudo -u "$RUN_USER" npm run build
  cd "$APP_DIR"
else
  echo "    frontend 未变化，跳过"
fi

echo "==> [5/7] 重启后端服务"
# 先做一次导入自检，语法/配置问题在这里就暴露，不必等到重启失败
if ! sudo -u "$RUN_USER" env $(cat "$APP_DIR/.env" | grep -v '^#' | xargs) \
     "$APP_DIR/venv/bin/python" -c "import app.main" 2>/tmp/import_err.txt; then
  echo "    ✗ 应用导入失败，已中止（服务仍在旧版本上运行）："
  sed -n '1,40p' /tmp/import_err.txt
  echo "    回滚命令：sudo -u $RUN_USER git reset --hard $PREV"
  exit 1
fi
sudo systemctl restart "$SVC"

echo "==> [6/7] 等待服务就绪"
for i in $(seq 1 30); do
  if curl -fsS "$HEALTH" >/dev/null 2>&1; then
    echo "    服务已就绪（第 ${i} 次探测）"
    break
  fi
  sleep 1
  if [ "$i" -eq 30 ]; then
    echo "    ✗ 30 秒内未就绪，最近日志："
    sudo journalctl -u "$SVC" -n 50 --no-pager
    echo "    回滚命令：sudo -u $RUN_USER git reset --hard $PREV && sudo systemctl restart $SVC"
    exit 1
  fi
done

echo "==> [7/7] 健康检查与对外验证"
echo -n "    本地 /health      : "; curl -s "$HEALTH"; echo
echo -n "    Nginx 首页 HTTP   : "; curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1/
echo -n "    服务状态          : "; systemctl is-active "$SVC"

echo
echo "✓ 更新完成：$PREV -> $NEW"
echo "  查看实时日志：sudo journalctl -u $SVC -f"
