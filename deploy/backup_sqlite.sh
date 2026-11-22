#!/bin/bash
set -euo pipefail

# Online SQLite WAL hot backup using sqlite3.Connection.backup()
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DB_PATH="${RGM_DB_PATH:-${ROOT_DIR}/backend/data/rgm.db}"
BACKUP_DIR="${RGM_BACKUP_DIR:-${ROOT_DIR}/backend/data/backups}"
RETENTION_DAYS="${RGM_BACKUP_RETENTION_DAYS:-14}"

mkdir -p "${BACKUP_DIR}"

if [ ! -f "${DB_PATH}" ]; then
  echo "[backup_sqlite] Database not found at ${DB_PATH}, skipping."
  exit 0
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
TMP_OUT="${BACKUP_DIR}/rgm_${STAMP}.db"

python3 - "${DB_PATH}" "${TMP_OUT}" <<'PYEOF'
import sqlite3, sys

src_path, dst_path = sys.argv[1], sys.argv[2]
src = sqlite3.connect(src_path, timeout=30.0)
dst = sqlite3.connect(dst_path)
try:
    with dst:
        src.backup(dst, pages=256, sleep=0.05)
    check = dst.execute("PRAGMA quick_check").fetchone()
    if not check or check[0] != "ok":
        raise RuntimeError(f"Backup integrity check failed: {check}")
finally:
    dst.close()
    src.close()
PYEOF

gzip -f "${TMP_OUT}"
echo "[backup_sqlite] Created verified hot backup: ${TMP_OUT}.gz"

# Prune backups older than RETENTION_DAYS
find "${BACKUP_DIR}" -type f -name "rgm_*.db.gz" -mtime +"${RETENTION_DAYS}" -delete 2>/dev/null || true
