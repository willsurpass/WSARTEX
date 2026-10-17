#!/usr/bin/env bash
# 在**独立测试库**上跑 Go 测试。
#
# 为什么不直接 `go test ./...`：测试的构造与清理是全局的（DELETE FROM assets
# WHERE id > X、按前缀删任务……），跑在开发库上会一点一点吃掉真实数据。
# 这个脚本把 DSN 指向 <库名>_test，测试造多少数据都只影响那个库。
#
# 用法：
#   ./test.sh                 跑全部
#   ./test.sh ./db/           只跑某个包
#   ./test.sh ./db/ -run TestX -v
set -euo pipefail
cd "$(dirname "$0")"

CONFIG_JSON="config.json"
if [[ ! -f "$CONFIG_JSON" ]]; then
  echo "找不到 config.json，无法确定数据库连接信息。" >&2
  exit 1
fi

# 从 config.json 读出连接参数（用 python3 解析，避免依赖 jq）。
read -r HOST PORT USER PASS DBNAME <<<"$(python3 - "$CONFIG_JSON" <<'PY'
import json, sys
c = json.load(open(sys.argv[1], encoding="utf-8")).get("database", {})
print(c.get("host", "127.0.0.1"), c.get("port", 5432), c.get("user", ""),
      c.get("password", ""), c.get("dbname", "wsartex"))
PY
)"

TEST_DB="${DBNAME}_test"
export WSARTEX_PG_DSN="postgres://${USER}:${PASS}@${HOST}:${PORT}/${TEST_DB}?sslmode=disable"
# 测试用的 JSON 配置必须与真实配置分家，否则 SetSetting 会改写操作者的设置。
export WSARTEX_DATA="$(mktemp -d "${TMPDIR:-/tmp}/wsartex-testconfig.XXXXXX")"
trap 'rm -rf "$WSARTEX_DATA"' EXIT

export GOFLAGS="-mod=vendor"
export GOPROXY=off

echo "[test] 目标库 ${TEST_DB} @ ${HOST}:${PORT}"
echo "[test] 配置目录 ${WSARTEX_DATA}"

# 没给包路径（无参数，或只给了 -count=1 这类 flag）时默认跑全部。
# go test 的参数顺序无关，但把 `.` 当默认包会让 `./test.sh -count=1` 只跑根目录
# 然后报 "no Go files"——那是个很容易踩、又很难看出原因的空转。
pkgs=()
for a in "$@"; do
  [[ "$a" == -* ]] || pkgs+=("$a")
done
if [[ ${#pkgs[@]} -eq 0 ]]; then
  set -- ./... "$@"
fi
go test "$@"
