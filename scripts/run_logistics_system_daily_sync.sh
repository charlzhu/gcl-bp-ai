#!/usr/bin/env bash
set -euo pipefail

# 功能：
#   发布服务器每日定时执行物流系统自动增量同步。
#
# 参数来源：
#   PYTHON_BIN：Python 解释器路径，生产环境建议指向虚拟环境 python。
#   LOGISTICS_SYNC_START_DATE：正式数据起始日期，默认 2026-01-01。
#   LOGISTICS_SYNC_OVERLAP_MINUTES：自动增量回看分钟数，默认 60。
#   LOGISTICS_SYNC_BATCH_SIZE：同步批大小，默认 1000。
#   LOGISTICS_SYNC_LOG_DIR：同步日志目录，默认 data/logs/logistics_sync。
#   LOGISTICS_SYNC_LOCK_FILE：同步锁文件路径，默认 /tmp/gcl-bp-ai-logistics-sync.lock。
#
# 返回值：
#   同步成功返回 0；同步失败返回非 0，crontab 可据此配合监控告警。

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
START_DATE="${LOGISTICS_SYNC_START_DATE:-2026-01-01}"
OVERLAP_MINUTES="${LOGISTICS_SYNC_OVERLAP_MINUTES:-60}"
BATCH_SIZE="${LOGISTICS_SYNC_BATCH_SIZE:-1000}"
LOG_DIR="${LOGISTICS_SYNC_LOG_DIR:-${ROOT_DIR}/data/logs/logistics_sync}"
LOCK_FILE="${LOGISTICS_SYNC_LOCK_FILE:-/tmp/gcl-bp-ai-logistics-sync.lock}"
LOG_FILE="${LOG_DIR}/daily-sync-$(date +%Y%m%d).log"

mkdir -p "${LOG_DIR}"
cd "${ROOT_DIR}"

run_sync() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] logistics daily sync start"
  "${PYTHON_BIN}" "${ROOT_DIR}/scripts/logistics_system_auto_sync.py" \
    --start-date "${START_DATE}" \
    --overlap-minutes "${OVERLAP_MINUTES}" \
    --batch-size "${BATCH_SIZE}"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] logistics daily sync finished"
}

if command -v flock >/dev/null 2>&1; then
  exec 9>"${LOCK_FILE}"
  if ! flock -n 9; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] previous logistics sync is still running, skip this run" >> "${LOG_FILE}"
    exit 0
  fi
  run_sync >> "${LOG_FILE}" 2>&1
else
  # 兼容不带 flock 的环境；生产 Linux 服务器建议安装 util-linux 以避免任务重入。
  run_sync >> "${LOG_FILE}" 2>&1
fi
