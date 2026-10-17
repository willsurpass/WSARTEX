#!/usr/bin/env bash
# =============================================================================
# WSARTEX 管理员密码重置脚本
#
# 登录用户名固定为 WSARTEX；密码以 bcrypt 哈希存放在数据库 settings 表的
# auth.password_hash 键。本脚本连上数据库后，用 pgcrypto 在库内生成 bcrypt 哈希
# 并写回该键——与后端登录校验（golang.org/x/crypto/bcrypt）完全兼容。
#
# 连接信息按以下优先级获取：
#   命令行参数 > --dsn/$WSARTEX_PG_DSN > config.json 的 database.*
# 重置后无需重启服务，直接用新密码登录即可。
#
# 用法示例：
#   ./reset-password.sh                          # 自动读 config.json/环境，交互输入新密码
#   ./reset-password.sh -p 'NewPass!'            # 直接给定新密码
#   ./reset-password.sh --dsn postgres://u:p@h:5432/wsartex
#   ./reset-password.sh -H 127.0.0.1 -P 5432 -U wsartex -W pass -d wsartex
#
# 安全：新密码经环境变量 + psql \getenv 传入（不进入进程 argv），并用 :'var'
# 自动转义（防 SQL 注入）；数据库密码经 PGPASSWORD 传递，同样不进 argv。
# =============================================================================
set -euo pipefail

PASS_KEY="auth.password_hash"
BCRYPT_COST=10

DSN=""
HOST="" PORT="" USER="" DBPASS="" DBNAME="" SSLMODE=""
CONFIG=""
NEWPASS=""
ASSUME_YES=0

die() { echo "错误：$*" >&2; exit 1; }
info() { echo "· $*" >&2; }

usage() { sed -n '2,21p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

# ---- 参数解析 -------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dsn)            DSN="${2:-}"; shift 2 ;;
    -H|--host)        HOST="${2:-}"; shift 2 ;;
    -P|--port)        PORT="${2:-}"; shift 2 ;;
    -U|--user)        USER="${2:-}"; shift 2 ;;
    -W|--db-password) DBPASS="${2:-}"; shift 2 ;;
    -d|--dbname)      DBNAME="${2:-}"; shift 2 ;;
    --sslmode)        SSLMODE="${2:-}"; shift 2 ;;
    --config)         CONFIG="${2:-}"; shift 2 ;;
    -p|--new-password) NEWPASS="${2:-}"; shift 2 ;;
    -y|--yes)         ASSUME_YES=1; shift ;;
    -h|--help)        usage ;;
    *) die "未知参数：$1（-h 查看用法）" ;;
  esac
done

# ---- 从 config.json 读取 database.*（仅 local 模式、且未显式给出连接时）-----
# 优先用 python3 解析（健壮）；缺 python3 时退回 grep（config.json 为规整分字段）。
read_config_json() {
  local path="$1"
  [[ -f "$path" ]] || return 1
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$path" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1])).get("database", {})
except Exception:
    sys.exit(1)
# 支持直接给 dsn，或分字段
if d.get("dsn"):
    print("DSN\t" + d["dsn"]); sys.exit(0)
for k in ("host","port","user","password","dbname","sslmode"):
    if d.get(k) is not None:
        print(k.upper() + "\t" + str(d[k]))
PY
  else
    # 极简后备：逐键 grep（值为字符串或数字）
    local k
    for k in host port user password dbname sslmode; do
      local v
      v=$(grep -oE "\"$k\"[[:space:]]*:[[:space:]]*(\"[^\"]*\"|[0-9]+)" "$path" 2>/dev/null \
            | head -1 | sed -E "s/.*:[[:space:]]*//; s/^\"//; s/\"$//") || true
      [[ -n "$v" ]] && echo -e "${k^^}\t$v"
    done
  fi
}

apply_config_fields() {
  local line key val
  while IFS=$'\t' read -r key val; do
    [[ -z "$key" ]] && continue
    case "$key" in
      DSN)      [[ -z "$DSN" ]] && DSN="$val" ;;
      HOST)     [[ -z "$HOST" ]] && HOST="$val" ;;
      PORT)     [[ -z "$PORT" ]] && PORT="$val" ;;
      USER)     [[ -z "$USER" ]] && USER="$val" ;;
      PASSWORD) [[ -z "$DBPASS" ]] && DBPASS="$val" ;;
      DBNAME)   [[ -z "$DBNAME" ]] && DBNAME="$val" ;;
      SSLMODE)  [[ -z "$SSLMODE" ]] && SSLMODE="$val" ;;
    esac
  done
}

# ---- 采集新密码 -----------------------------------------------------------
if [[ -z "$NEWPASS" ]]; then
  read -r -s -p "输入新密码（用户名固定为 WSARTEX）：" NEWPASS; echo >&2
  [[ -n "$NEWPASS" ]] || die "密码不能为空"
  read -r -s -p "再次输入以确认：" NEWPASS2; echo >&2
  [[ "$NEWPASS" == "$NEWPASS2" ]] || die "两次输入不一致"
fi
[[ -n "$NEWPASS" ]] || die "密码不能为空"

# 通过环境变量把密码交给 psql（\getenv 读取，不进入 argv/ps）
export WSARTEX_RESET_NEWPASS="$NEWPASS"

# 库内生成 bcrypt 并 upsert；密码用 :'newpw' 自动转义。CREATE EXTENSION 幂等，
# 若数据库角色无建扩展权限会在此报错（提示见下方 run 的失败分支）。
SQL=$(cat <<SQL
\\set ON_ERROR_STOP on
\\getenv newpw WSARTEX_RESET_NEWPASS
CREATE EXTENSION IF NOT EXISTS pgcrypto;
INSERT INTO settings(key, value)
VALUES ('$PASS_KEY', crypt(:'newpw', gen_salt('bf', $BCRYPT_COST)))
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now();
SQL
)

# ---- 执行 -----------------------------------------------------------------
# 连接信息优先级：命令行 > --dsn/$WSARTEX_PG_DSN > config.json
if [[ -z "$DSN" && -z "$HOST$USER$DBNAME" ]]; then
  [[ -n "${WSARTEX_PG_DSN:-}" ]] && DSN="$WSARTEX_PG_DSN"
fi
if [[ -z "$DSN" && -z "$HOST$USER$DBNAME" ]]; then
  cfg="${CONFIG:-config.json}"
  if [[ -f "$cfg" ]]; then
    info "从 $cfg 读取数据库配置"
    apply_config_fields < <(read_config_json "$cfg")
  fi
fi

command -v psql >/dev/null 2>&1 || die "本机未找到 psql（brew install postgresql@16，或安装 postgresql-client）"

declare -a PSQL_ARGS=()
if [[ -n "$DSN" ]]; then
  PSQL_ARGS=("$DSN")
  target="$DSN"
else
  [[ -n "$USER"   ]] || die "缺少数据库用户（-U）或有效的 config.json/DSN"
  [[ -n "$DBNAME" ]] || die "缺少数据库名（-d）或有效的 config.json/DSN"
  HOST="${HOST:-127.0.0.1}"; PORT="${PORT:-5432}"; SSLMODE="${SSLMODE:-disable}"
  PSQL_ARGS=(-h "$HOST" -p "$PORT" -U "$USER" -d "$DBNAME")
  [[ -n "$SSLMODE" ]] && export PGSSLMODE="$SSLMODE"
  [[ -n "$DBPASS" ]] && export PGPASSWORD="$DBPASS"
  target="$USER@$HOST:$PORT/$DBNAME"
fi

info "目标数据库：$target"
if [[ "$ASSUME_YES" -ne 1 ]]; then
  read -r -p "确认在该库重置 WSARTEX 密码？[y/N] " ans
  [[ "$ans" == "y" || "$ans" == "Y" ]] || die "已取消"
fi

if ! printf '%s\n' "$SQL" | psql "${PSQL_ARGS[@]}" -v ON_ERROR_STOP=1 -q >/dev/null; then
  die "写入失败。若报 pgcrypto 权限/缺失，请用具备建扩展权限的角色，或先手动执行 CREATE EXTENSION pgcrypto。"
fi

unset WSARTEX_RESET_NEWPASS
echo "✓ 已重置 WSARTEX 管理员密码。请用用户名 WSARTEX + 新密码登录（无需重启服务）。"
