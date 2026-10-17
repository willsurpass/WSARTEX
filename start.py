#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WSARTEX 启动器（跨平台：macOS / Linux / Windows）
=================================================

前置要求：本机需先安装 Python 3.8 或更高版本（详见 README）。
用法：双击本文件，或在项目根目录执行 `python3 start.py`

流程：
  1. 识别当前操作系统
  2. 检测外部依赖（Go / Node / npm / PostgreSQL，以及可选的 nmap、ripgrep）
  3. 若有缺失 → 让用户选择：① 退出自行安装  ② 由脚本自动安装
  4. 安装完成后 → 让用户选择：① 退出  ② 启动 WSARTEX
  5. 若无缺失 → 直接启动 WSARTEX，并自动打开浏览器进入管理界面

停止服务：运行 quit.py。

本脚本不改动项目源码；构建产物与运行数据分别落在 server/webui/dist、data/ 与根目录二进制。
"""

from __future__ import annotations

import json
import os
import platform
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ───────────────────────────── 常量 ─────────────────────────────

PROJECT = Path(__file__).resolve().parent
DATA_DIR = PROJECT / "data"
LOG_FILE = DATA_DIR / "wsartex-launcher.log"
PID_FILE = DATA_DIR / "wsartex-launcher.pid"
BIN_NAME = "wsartex.exe" if os.name == "nt" else "wsartex"
BIN_PATH = PROJECT / BIN_NAME
DIST_DIR = PROJECT / "server" / "webui" / "dist"
WEB_DIR = PROJECT / "web"

ADDR = "127.0.0.1:8787"
PORT = 8787
PROXY_PORT = 8788
HEALTH_URL = f"http://{ADDR}/api/health"
AUTH_URL = f"http://{ADDR}/api/auth/status"
HEALTH_TIMEOUT = 120  # 秒；首次启动需跑数据库 schema 迁移与种子数据

PG_PORT = 5432
PG_DB = "wsartex"
PG_ROLE = "wsartex"
PG_PACKAGE_BREW = "postgresql@16"

IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")
IS_WIN = os.name == "nt"

C_OK, C_BAD, C_WARN, C_TITLE, C_BOLD, C_END = (
    "\033[32m", "\033[31m", "\033[33m", "\033[1;36m", "\033[1m", "\033[0m",
)


# ───────────────────────────── 终端输出 ─────────────────────────────

def _enable_color() -> None:
    """Windows 10+ 控制台默认不解析 ANSI，需要显式开启；不支持时自动降级为无色。"""
    global C_OK, C_BAD, C_WARN, C_TITLE, C_BOLD, C_END
    if IS_WIN:
        try:
            import ctypes
            k = ctypes.windll.kernel32
            k.SetConsoleMode(k.GetStdHandle(-11), 7)
        except Exception:
            C_OK = C_BAD = C_WARN = C_TITLE = C_BOLD = C_END = ""


def ui_ok(t: str) -> None: print(f"  {C_OK}✓{C_END} {t}")
def ui_info(t: str) -> None: print(f"  · {t}")
def ui_warn(t: str) -> None: print(f"  {C_WARN}⚠{C_END} {t}")
def ui_fail(t: str) -> None: print(f"  {C_BAD}✗{C_END} {t}")
def ui_step(no: int, t: str) -> None: print(f"\n{C_TITLE}━━━ 第 {no} 步 · {t} ━━━{C_END}")
def ui_title(t: str) -> None: print(f"\n{C_TITLE}{t}{C_END}")


def die(msg: str, hint: str = "", code: int = 1) -> None:
    ui_fail(msg)
    if hint:
        print(f"  补救：{hint}")
    pause_if_double_clicked()
    sys.exit(code)


def pause_if_double_clicked() -> None:
    """双击运行时窗口会在脚本结束后立刻关闭，留一次回车让用户看清信息。"""
    if sys.stdin is not None and sys.stdin.isatty():
        try:
            input("\n按回车键结束…")
        except (EOFError, KeyboardInterrupt):
            pass


def ask_choice(title: str, options: List[str], default: int = 1) -> int:
    """让用户从编号选项中选择，返回 1..N。无法交互时返回 default。"""
    print()
    ui_title(title)
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    if not (sys.stdin and sys.stdin.isatty()):
        ui_info(f"（非交互环境，默认选择 {default}）")
        return default
    while True:
        try:
            raw = input(f"\n请输入序号 [{default}]：").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return default
        if raw == "":
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw)
        ui_warn(f"请输入 1 到 {len(options)} 之间的数字")


# ───────────────────────────── 通用工具 ─────────────────────────────

def run(cmd: List[str], cwd: Path = PROJECT, env: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None, quiet: bool = False) -> Tuple[int, str]:
    """执行命令；返回 (退出码, 输出)。quiet=True 时不透传到终端。"""
    if not quiet:
        print(f"  {C_BOLD}$ {' '.join(str(c) for c in cmd)}{C_END}")
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    try:
        if quiet:
            p = subprocess.run(cmd, cwd=cwd, env=full_env, capture_output=True,
                               text=True, timeout=timeout)
            return p.returncode, (p.stdout or "").strip()
        p = subprocess.run(cmd, cwd=cwd, env=full_env, timeout=timeout)
        return p.returncode, ""
    except FileNotFoundError:
        return 127, ""
    except subprocess.TimeoutExpired:
        ui_fail(f"命令超时（{timeout}s）：{' '.join(str(c) for c in cmd)}")
        return 124, ""


def which(name: str) -> Optional[str]:
    """在 PATH 中查找可执行文件；Windows 下额外尝试常见安装目录。"""
    found = shutil.which(name)
    if found:
        return found
    if IS_WIN:
        for base in (r"C:\Program Files", r"C:\Program Files (x86)"):
            for sub in (r"Go\bin", r"nodejs", r"PostgreSQL\16\bin", r"PostgreSQL\15\bin"):
                cand = Path(base) / sub / f"{name}.exe"
                if cand.exists():
                    return str(cand)
    return None


def newest_mtime(path: Path) -> float:
    """文件取自身 mtime；目录取整棵树最新 mtime；不存在返回 0。"""
    try:
        if path.is_file():
            return path.stat().st_mtime
        if path.is_dir():
            best = 0.0
            for p in path.rglob("*"):
                try:
                    best = max(best, p.stat().st_mtime)
                except OSError:
                    pass
            return best
    except OSError:
        pass
    return 0.0


def http_json(url: str, timeout: int = 3) -> Optional[Dict]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None


def health_ok() -> bool:
    """只有响应体明确是本项目服务才算已运行，避免误判占用同端口的其他程序。"""
    data = http_json(HEALTH_URL)
    return bool(data) and data.get("service") == "wsartex"


def port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def log_tail(n: int = 30) -> str:
    try:
        lines = LOG_FILE.read_text(errors="replace").splitlines()
        return "\n".join("    | " + line for line in lines[-n:])
    except OSError:
        return "    | （暂无日志）"


def tool_version(cmd: List[str]) -> str:
    rc, out = run(cmd, quiet=True, timeout=20)
    if rc != 0 or not out:
        return ""
    return out.splitlines()[0].strip()


# ───────────────────────────── 操作系统识别 ─────────────────────────────

def detect_os() -> Tuple[str, str]:
    """返回 (系统标识, 可读名称)。"""
    if IS_MAC:
        try:
            ver = platform.mac_ver()[0] or ""
        except Exception:
            ver = ""
        return "macos", f"macOS {ver}".strip()
    if IS_LINUX:
        name = ""
        try:
            for line in Path("/etc/os-release").read_text(errors="replace").splitlines():
                if line.startswith("PRETTY_NAME="):
                    name = line.split("=", 1)[1].strip().strip('"')
                    break
        except OSError:
            pass
        return "linux", name or "Linux"
    if IS_WIN:
        return "windows", f"Windows {platform.release()}"
    return "unknown", platform.platform()


def linux_pkg_manager() -> Optional[str]:
    for mgr in ("apt-get", "dnf", "yum", "pacman", "zypper", "apk"):
        if which(mgr):
            return mgr
    return None


# ───────────────────────────── 依赖检测 ─────────────────────────────

# (键, 显示名, 是否必需, 说明)
DEPENDENCIES = [
    ("go",   "Go（编译后端）",        True,  "编译 Go 后端所需的工具链"),
    ("node", "Node.js（构建前端）",    True,  "构建 Next.js 前端所需的运行时"),
    ("npm",  "npm（安装前端依赖）",    True,  "随 Node.js 一起安装"),
    ("psql", "PostgreSQL 客户端",      True,  "连接数据库；服务端未装时会一并安装"),
    ("nmap", "nmap（可选）",           False, "资产扫描常用工具，缺失不影响启动"),
    ("rg",   "ripgrep（可选）",        False, "快速检索工具，缺失不影响启动"),
]


def check_deps() -> Tuple[List[Tuple[str, str, bool, str]], List[Tuple[str, str, bool, str]]]:
    """返回 (缺失项, 已安装项)。"""
    missing, present = [], []
    for item in DEPENDENCIES:
        if which(item[0]):
            present.append(item)
        else:
            missing.append(item)
    return missing, present


def print_dep_report(missing, present) -> None:
    if present:
        for key, name, req, _ in present:
            path = which(key) or ""
            ui_ok(f"{name}：{path}")
    for key, name, req, note in missing:
        if req:
            ui_fail(f"{name} —— 缺失（{note}）")
        else:
            ui_warn(f"{name} —— 缺失（{note}）")


# ───────────────────────────── 依赖安装 ─────────────────────────────

def install_cmd_for(os_kind: str) -> Tuple[Optional[List[str]], Optional[List[str]], str]:
    """返回 (必需依赖安装命令, 可选依赖安装命令, 手动安装说明)。"""
    if os_kind == "macos":
        manual = ("先安装 Homebrew（https://brew.sh），然后执行：\n"
                  f"      brew install go node {PG_PACKAGE_BREW}\n"
                  "      brew install nmap ripgrep   # 可选")
        if not which("brew"):
            return None, None, manual
        required = ["brew", "install", "go", "node", PG_PACKAGE_BREW]
        optional = ["brew", "install", "nmap", "ripgrep"]
        return required, optional, manual

    if os_kind == "linux":
        mgr = linux_pkg_manager()
        if not mgr:
            return None, None, "未识别到包管理器，请用发行版自带的方式安装 go / nodejs / npm / postgresql。"
        if mgr == "apt-get":
            prefix = ["sudo"] if os.geteuid() != 0 else []
            return (prefix + ["apt-get", "install", "-y", "golang-go", "nodejs", "npm", "postgresql"],
                    prefix + ["apt-get", "install", "-y", "nmap", "ripgrep"],
                    "sudo apt-get update && sudo apt-get install -y golang-go nodejs npm postgresql")
        if mgr in ("dnf", "yum"):
            prefix = ["sudo"] if os.geteuid() != 0 else []
            return (prefix + [mgr, "install", "-y", "golang", "nodejs", "npm", "postgresql-server"],
                    prefix + [mgr, "install", "-y", "nmap", "ripgrep"],
                    f"sudo {mgr} install -y golang nodejs npm postgresql-server")
        if mgr == "pacman":
            prefix = ["sudo"] if os.geteuid() != 0 else []
            return (prefix + ["pacman", "-S", "--noconfirm", "go", "nodejs", "npm", "postgresql"],
                    prefix + ["pacman", "-S", "--noconfirm", "nmap", "ripgrep"],
                    "sudo pacman -S --noconfirm go nodejs npm postgresql")
        if mgr == "apk":
            return (["apk", "add", "go", "nodejs", "npm", "postgresql"],
                    ["apk", "add", "nmap", "ripgrep"],
                    "apk add go nodejs npm postgresql")
        if mgr == "zypper":
            prefix = ["sudo"] if os.geteuid() != 0 else []
            return (prefix + ["zypper", "install", "-y", "go", "nodejs", "npm", "postgresql-server"],
                    prefix + ["zypper", "install", "-y", "nmap", "ripgrep"],
                    "sudo zypper install -y go nodejs npm postgresql-server")
        return None, None, f"请用 {mgr} 安装 go / nodejs / npm / postgresql。"

    if os_kind == "windows":
        if which("winget"):
            return (["winget", "install", "--accept-source-agreements", "--accept-package-agreements",
                     "GoLang.Go", "OpenJS.NodeJS.LTS", "PostgreSQL.PostgreSQL.16"],
                    ["winget", "install", "--accept-source-agreements", "--accept-package-agreements",
                     "Insecure.Nmap", "BurntSushi.ripgrep.MSVC"],
                    "winget install GoLang.Go OpenJS.NodeJS.LTS PostgreSQL.PostgreSQL.16")
        if which("choco"):
            return (["choco", "install", "-y", "golang", "nodejs-lts", "postgresql16"],
                    ["choco", "install", "-y", "nmap", "ripgrep"],
                    "choco install -y golang nodejs-lts postgresql16")
        if which("scoop"):
            return (["scoop", "install", "go", "nodejs-lts", "postgresql"],
                    ["scoop", "install", "nmap", "ripgrep"],
                    "scoop install go nodejs-lts postgresql")
        return None, None, ("未检测到 winget / choco / scoop。请手动安装 Go、Node.js 与 PostgreSQL 后重新运行本脚本。\n"
                            "      Go：https://go.dev/dl/    Node.js：https://nodejs.org/    PostgreSQL：https://www.postgresql.org/download/windows/")

    return None, None, "无法识别的操作系统，请手动安装 Go / Node.js / PostgreSQL。"


def install_deps(os_kind: str) -> bool:
    """自动安装缺失依赖；返回是否全部就绪。"""
    missing, _ = check_deps()
    if not missing:
        return True

    required_cmd, optional_cmd, manual = install_cmd_for(os_kind)
    if required_cmd is None:
        ui_fail("无法在本系统上自动安装依赖。")
        print(f"  请手动安装：\n      {manual}")
        return False

    need_optional = any(not req for _, _, req, _ in missing)
    need_required = any(req for _, _, req, _ in missing)

    if need_required:
        print()
        ui_info("开始安装必需依赖（需要联网，可能耗时数分钟）…")
        print(f"  {C_BOLD}$ {' '.join(required_cmd)}{C_END}")
        rc, _ = run(required_cmd, timeout=None)
        if rc != 0:
            ui_fail("依赖安装失败。")
            print(f"  请手动安装：\n      {manual}")
            return False
        ui_ok("必需依赖安装完成")

    if need_optional and optional_cmd:
        print()
        ui_info("尝试安装可选工具（失败不影响使用）…")
        rc, _ = run(optional_cmd, timeout=None)
        if rc == 0:
            ui_ok("可选工具安装完成")
        else:
            ui_warn("可选工具安装失败，已跳过")

    # 安装后重新解析 PATH：包管理器刚装好的东西可能不在当前进程的 PATH 缓存里
    return True


def install_optional(os_kind: str) -> None:
    """只安装可选工具（nmap / ripgrep）。失败仅告警，绝不阻断启动。"""
    _, optional_cmd, _ = install_cmd_for(os_kind)
    if not optional_cmd:
        ui_warn("无法在本系统上自动安装可选工具，已跳过")
        return
    print()
    ui_info("安装可选工具（需要联网，可能耗时几分钟）…")
    print(f"  {C_BOLD}$ {' '.join(optional_cmd)}{C_END}")
    rc, _ = run(optional_cmd, timeout=None)
    if rc != 0:
        ui_warn("可选工具安装失败，已跳过（不影响使用）")
        return
    # 装完再确认一次：新可执行文件未必立刻进入当前进程的 PATH
    _, present = check_deps()
    have = [t for t in ("nmap", "rg") if which(t)]
    if have:
        ui_ok("可选工具已就绪：" + "、".join(have))
    else:
        ui_warn("安装已完成，但本终端尚未识别到新命令；重开窗口后即可生效")


# ───────────────────────────── PostgreSQL ─────────────────────────────

def pg_bin_dir() -> Optional[Path]:
    """定位 PostgreSQL 的 bin 目录（macOS 的 brew 版是 keg-only，不在 PATH 里）。"""
    psql = which("psql")
    if psql:
        return Path(psql).parent
    if IS_MAC and which("brew"):
        rc, prefix = run(["brew", "--prefix", PG_PACKAGE_BREW], quiet=True)
        if rc == 0 and prefix:
            cand = Path(prefix) / "bin"
            if (cand / "psql").exists():
                return cand
    if IS_WIN:
        for base in (r"C:\Program Files\PostgreSQL", r"C:\Program Files (x86)\PostgreSQL"):
            p = Path(base)
            if p.is_dir():
                for ver in sorted(p.iterdir(), reverse=True):
                    cand = ver / "bin"
                    if (cand / "psql.exe").exists():
                        return cand
    if IS_LINUX:
        for cand in (Path("/usr/lib/postgresql"), Path("/usr/pgsql")):
            if cand.is_dir():
                for ver in sorted(cand.iterdir(), reverse=True):
                    b = ver / "bin"
                    if (b / "psql").exists():
                        return b
    return None


def pg_ready() -> bool:
    rc, _ = run(["pg_isready", "-h", "127.0.0.1", "-p", str(PG_PORT)], quiet=True, timeout=20)
    return rc == 0


def start_pg_service(os_kind: str) -> None:
    if os_kind == "macos" and which("brew"):
        rc, _ = run(["brew", "services", "start", PG_PACKAGE_BREW], quiet=True, timeout=180)
        if rc == 0:
            ui_ok(f"已启动 {PG_PACKAGE_BREW} 服务")
            return
    if os_kind == "linux":
        for unit in ("postgresql", "postgresql-16", "postgresql.service"):
            prefix = ["sudo"] if os.geteuid() != 0 else []
            rc, _ = run(prefix + ["systemctl", "start", unit], quiet=True, timeout=120)
            if rc == 0:
                ui_ok(f"已启动 {unit} 服务")
                return
    if os_kind == "windows":
        for svc in ("postgresql-x64-16", "postgresql-x64-15", "postgresql"):
            rc, _ = run(["net", "start", svc], quiet=True, timeout=120)
            if rc == 0:
                ui_ok(f"已启动服务 {svc}")
                return
    ui_warn("未能自动启动 PostgreSQL 服务，尝试直接连接…")


def step_postgres(os_kind: str) -> Optional[str]:
    """准备 PostgreSQL：启动服务、建角色、建库。返回新建角色的密码（未新建则为 None）。"""
    ui_step(3, f"准备 PostgreSQL（127.0.0.1:{PG_PORT}）")

    if not pg_ready():
        ui_info("PostgreSQL 未在运行，尝试启动服务…")
        start_pg_service(os_kind)
        deadline = time.time() + 60
        while time.time() < deadline:
            if pg_ready():
                break
            time.sleep(1)
        else:
            die(
                "PostgreSQL 未能在 60 秒内就绪。",
                "排查：确认服务已启动（macOS: brew services list；Linux: systemctl status postgresql；"
                "Windows: 服务管理器），或手动启动后重新运行 start.py。",
            )
    ui_ok(f"PostgreSQL 已在 127.0.0.1:{PG_PORT} 运行")

    bindir = pg_bin_dir()
    psql = str(bindir / ("psql.exe" if IS_WIN else "psql")) if bindir else (which("psql") or "psql")

    def query(sql: str) -> str:
        _, out = run([psql, "-h", "127.0.0.1", "-p", str(PG_PORT), "-d", "postgres", "-tAc", sql],
                     quiet=True, timeout=60)
        return out

    role_exists = bool(query(f"SELECT 1 FROM pg_roles WHERE rolname='{PG_ROLE}'"))
    config_exists = (PROJECT / "config.json").exists()
    created_pw: Optional[str] = None

    if role_exists and config_exists:
        ui_ok(f"角色 {PG_ROLE} 与 config.json 均已存在，保持不动")
    else:
        created_pw = "".join(secrets.choice(
            "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789") for _ in range(24))
        sql = (f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{PG_ROLE}') "
               f"THEN CREATE ROLE {PG_ROLE} LOGIN CREATEDB; END IF; END $$;"
               f" ALTER ROLE {PG_ROLE} WITH LOGIN CREATEDB PASSWORD '{created_pw}'")
        rc, _ = run([psql, "-h", "127.0.0.1", "-p", str(PG_PORT), "-d", "postgres",
                     "-v", "ON_ERROR_STOP=1", "-c", sql], quiet=True, timeout=60)
        if rc != 0:
            die(f"创建/更新数据库角色 {PG_ROLE} 失败。",
                f'手动执行：psql -d postgres -c "CREATE ROLE {PG_ROLE} LOGIN PASSWORD \'你的密码\' CREATEDB"')
        ui_ok(f"角色 {PG_ROLE} 已{'同步新密码' if role_exists else '创建'}")

    if query(f"SELECT 1 FROM pg_database WHERE datname='{PG_DB}'"):
        ui_ok(f"数据库 {PG_DB} 已存在")
    else:
        createdb = str(bindir / ("createdb.exe" if IS_WIN else "createdb")) if bindir else "createdb"
        rc, _ = run([createdb, "-h", "127.0.0.1", "-p", str(PG_PORT), "-O", PG_ROLE, PG_DB],
                    quiet=True, timeout=60)
        if rc != 0:
            die(f"创建数据库 {PG_DB} 失败。",
                f"手动执行：createdb -h 127.0.0.1 -p {PG_PORT} -O {PG_ROLE} {PG_DB}")
        ui_ok(f"数据库 {PG_DB} 已创建")

    env = {"PGPASSWORD": created_pw} if created_pw else None
    rc, out = run([psql, "-h", "127.0.0.1", "-p", str(PG_PORT), "-U", PG_ROLE, "-d", PG_DB,
                   "-tAc", "select 1"], quiet=True, env=env, timeout=60)
    if rc != 0:
        die(f"以 {PG_ROLE} 身份连接数据库失败：{out}",
            f"手动排查：psql -h 127.0.0.1 -p {PG_PORT} -U {PG_ROLE} -d {PG_DB} -c 'select 1'")
    ui_ok(f"连接验收通过（{PG_ROLE} @ 127.0.0.1:{PG_PORT}/{PG_DB}）")
    return created_pw


# ───────────────────────────── config.json ─────────────────────────────

def step_config(created_pw: Optional[str]) -> None:
    ui_step(4, "生成 config.json（已存在则不覆盖）")
    cfg = PROJECT / "config.json"
    if cfg.exists():
        try:
            db = json.loads(cfg.read_text())
            d = db.get("database", {})
            ui_ok(f"config.json 已存在，直接复用（{d.get('user', '?')}@{d.get('host', '?')}:"
                  f"{d.get('port', '?')}/{d.get('dbname', '?')}）")
        except (ValueError, AttributeError):
            die("config.json 存在但解析失败。", "手动修复或备份后删除该文件，再重新运行 start.py。")
        return
    if created_pw is None:
        die(
            f"角色 {PG_ROLE} 已存在但 config.json 缺失，脚本无法得知其密码。",
            "手动创建 config.json（参考 config.example.json：host=127.0.0.1、"
            f"port={PG_PORT}、user={PG_ROLE}、dbname={PG_DB}、sslmode=disable、password=角色密码；不要写 skill_dir）。",
        )
    content = {"database": {"host": "127.0.0.1", "port": PG_PORT, "user": PG_ROLE,
                            "password": created_pw, "dbname": PG_DB, "sslmode": "disable"}}
    tmp = cfg.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, cfg)
    ui_ok("config.json 已生成（含数据库密码，未加入版本控制）")


# ───────────────────────────── 前端构建 ─────────────────────────────

def need_npm_ci() -> bool:
    nm = WEB_DIR / "node_modules"
    if not nm.exists():
        return True
    marker = nm / ".package-lock.json"
    lock = WEB_DIR / "package-lock.json"
    if not marker.exists():
        return True
    return newest_mtime(lock) > newest_mtime(marker) or newest_mtime(WEB_DIR / "package.json") > newest_mtime(marker)


def need_next_build() -> bool:
    index = DIST_DIR / "index.html"
    if not index.exists() or index.stat().st_size < 1024:
        return True
    inputs = [WEB_DIR / p for p in ("src", "public", "package.json", "package-lock.json",
                                    "next.config.mjs", "postcss.config.mjs", "tsconfig.json",
                                    "tsconfig.scripts.json", "components.json", "biome.json")]
    return max(newest_mtime(p) for p in inputs) > newest_mtime(index)


def step_frontend() -> None:
    ui_step(5, "构建前端（Next.js 静态导出）")
    env = {"HUSKY": "0", "NEXT_TELEMETRY_DISABLED": "1"}

    if need_npm_ci():
        ui_info("安装前端依赖（优先使用项目内离线缓存，无需联网）…")
        cmd = ["npm", "ci", "--no-audit", "--no-fund"]
        if (WEB_DIR / ".npm-cache").is_dir():
            cmd += ["--offline", "--cache", ".npm-cache"]
        rc, _ = run(cmd, cwd=WEB_DIR, env=env, timeout=1800)
        if rc != 0:
            ui_warn("离线安装失败，尝试联网安装…")
            rc, _ = run(["npm", "ci", "--no-audit", "--no-fund"], cwd=WEB_DIR, env=env, timeout=1800)
            if rc != 0:
                die("npm ci 失败。", "检查网络后手动执行：cd web && npm ci")
        ui_ok("前端依赖安装完成")
    else:
        ui_ok("前端依赖已就绪，跳过安装")

    if need_next_build():
        ui_info("静态导出前端（首次或源码变动时执行，可能耗时数分钟）…")
        rc, _ = run(["npm", "run", "build:static"], cwd=WEB_DIR, env=env, timeout=1800)
        if rc != 0:
            if (DIST_DIR / "index.html").exists():
                ui_warn("本次前端构建失败，沿用上一次的产物继续")
            else:
                die("前端构建失败。", "手动执行：cd web && npm run build:static 查看完整报错。")
        else:
            if DIST_DIR.exists():
                shutil.rmtree(DIST_DIR)
            shutil.copytree(WEB_DIR / "out", DIST_DIR)
            if not (DIST_DIR / "index.html").exists() or not (DIST_DIR / "_next").exists():
                die("前端产物验收失败（index.html 或 _next 缺失）。", "检查 web/out 目录内容。")
            ui_ok("前端构建完成并已内嵌到后端目录")
    else:
        ui_ok("前端产物已是最新，跳过构建")


# ───────────────────────────── 后端编译 ─────────────────────────────

def need_go_build() -> bool:
    if not BIN_PATH.exists():
        return True
    exe_m = newest_mtime(BIN_PATH)
    dirs = [PROJECT / d for d in (
        "cmd", "server", "agent", "db", "config", "traffic", "guard", "intercept",
        "llmpool", "llmrec", "notify", "report", "evidence", "enrich",
        "sidequestion", "mcphttp", "third_party",
    )]
    src = max([newest_mtime(d) for d in dirs]
              + [newest_mtime(PROJECT / "go.mod"), newest_mtime(PROJECT / "go.sum")])
    return max(src, newest_mtime(DIST_DIR)) > exe_m


def step_backend() -> None:
    ui_step(6, "编译后端（go build）")
    if not need_go_build():
        ui_ok("后端二进制已是最新，跳过编译")
        return

    ui_info("编译中（项目已内置全部依赖，无需联网；首次可能耗时数分钟）…")
    env = {"CGO_ENABLED": "0"}
    if (PROJECT / "vendor").is_dir():
        env["GOFLAGS"] = "-mod=vendor"
    out = PROJECT / (BIN_NAME + ".new")
    if out.exists():
        out.unlink()
    # 版本号打进二进制，便于从 /api/health 与页面顶栏认出本次构建
    stamp = time.strftime("local-%Y%m%d-%H%M")
    rc, _ = run(["go", "build", "-tags", "embedui", "-trimpath",
                 "-ldflags", f"-s -w -X main.version={stamp}",
                 "-o", out.name, "./cmd/wsartex"],
                env=env, timeout=2400)
    if rc != 0:
        if out.exists():
            out.unlink()
        die("Go 编译失败（已清理临时产物，不会留下坏二进制）。",
            "常见原因：Go 版本低于 go.mod 要求、或 vendor 目录与 go.mod 不一致（可尝试 go mod vendor）。")
    try:
        os.chmod(out, 0o755)
    except OSError:
        pass
    os.replace(out, BIN_PATH)
    ui_ok(f"后端二进制已生成（{BIN_NAME}）")


# ───────────────────────────── 启动与健康检查 ─────────────────────────────

def step_start() -> bool:
    """启动服务。返回 True 表示本次由脚本拉起，False 表示复用了已有实例。"""
    ui_step(7, "启动 WSARTEX")
    if health_ok():
        ui_ok(f"检测到 WSARTEX 已在运行于 http://{ADDR}，直接复用")
        return False

    if port_busy(PORT):
        die(f"端口 {PORT} 已被其他程序占用。",
            f"排查占用进程后重试（macOS/Linux: lsof -nP -iTCP:{PORT}；Windows: netstat -ano | findstr {PORT}）。")

    proxy = PROXY_PORT
    if port_busy(proxy):
        for p in range(proxy + 1, proxy + 20):
            if not port_busy(p):
                ui_warn(f"流量代理端口 {proxy} 被占用，改用 {p}")
                proxy = p
                break
        else:
            proxy = 0
            ui_warn("流量代理端口全部被占用，本次禁用流量录制")

    DATA_DIR.mkdir(exist_ok=True)
    log_fh = open(LOG_FILE, "ab", buffering=0)
    # 直接拉起 wsartex 二进制，不再经过 start.sh / start.bat——那两个壳脚本已删除，
    # 启动与停止只由 start.py / quit.py 负责。原先壳脚本提供的"崩溃后退避重启"
    # 一并去掉：本地工具不需要守护进程语义，崩溃了就重新运行 start.py，
    # 让失败直接暴露在日志和终端里，比一个悄悄重启的守护进程好排查。
    args = ["-addr", ADDR]
    if proxy:
        args += ["-proxy", f"127.0.0.1:{proxy}"]
    if IS_WIN:
        creation = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        proc = subprocess.Popen([str(BIN_PATH)] + args, cwd=str(PROJECT), stdin=subprocess.DEVNULL,
                                stdout=log_fh, stderr=subprocess.STDOUT, creationflags=creation)
    else:
        proc = subprocess.Popen([str(BIN_PATH)] + args, cwd=str(PROJECT), stdin=subprocess.DEVNULL,
                                stdout=log_fh, stderr=subprocess.STDOUT, start_new_session=True)
    PID_FILE.write_text(str(proc.pid) + "\n")
    ui_ok(f"已后台启动（守护进程 PID {proc.pid}，日志 data/{LOG_FILE.name}）")

    ui_info(f"等待服务就绪（最多 {HEALTH_TIMEOUT} 秒，首次启动需初始化数据库）…")
    deadline = time.time() + HEALTH_TIMEOUT
    while time.time() < deadline:
        if health_ok():
            ui_ok("服务就绪")
            return True
        time.sleep(2)

    tail = log_tail()
    die(f"服务未能在 {HEALTH_TIMEOUT} 秒内就绪。\n日志末尾：\n{tail}",
        f"查看完整日志：{LOG_FILE}；常见原因：数据库密码不匹配、PostgreSQL 未运行。修复后重新运行 start.py。")


# ───────────────────────────── 打开浏览器与引导 ─────────────────────────────

def open_browser(url: str) -> None:
    try:
        if IS_MAC:
            subprocess.Popen(["open", url])
        elif IS_WIN:
            os.startfile(url)  # type: ignore[attr-defined]
        else:
            if which("xdg-open"):
                subprocess.Popen(["xdg-open", url])
            else:
                ui_warn(f"未找到 xdg-open，请手动用浏览器访问 {url}")
                return
        ui_ok(f"已在默认浏览器打开 {url}")
    except Exception as e:
        ui_warn(f"自动打开浏览器失败（{e}），请手动访问 {url}")


def step_open() -> None:
    ui_step(8, "打开管理界面")
    auth = http_json(AUTH_URL)
    first = auth is not None and not auth.get("initialized")
    url = f"http://{ADDR}/setup" if first else f"http://{ADDR}"
    open_browser(url)

    print()
    if first:
        ui_title("★ 首次使用引导")
        print("  1. 浏览器已打开「设置管理员密码」页面")
        print("     设置一个至少 8 位的密码；登录用户名固定为：WSARTEX")
        print("  2. 登录后进入「系统 → LLM 配置」，添加并激活你的 LLM")
        print("     LLM 是自主探索的核心，没有它任务不会开跑")
        print("  3. 只对本地隔离靶场创建任务；建议首次把 worker 数调为 1 观察行为")
    elif auth is None:
        ui_warn("暂时无法读取初始化状态，浏览器会自动跳转到登录页")
    else:
        ui_title("登录提示")
        print("  服务已初始化，直接在浏览器登录即可（用户名 WSARTEX）")
        print("  未配置 LLM 时请到「系统 → LLM 配置」添加并激活")

    print()
    ui_title("★ 常用操作")
    print(f"  管理界面    ：http://{ADDR}")
    print("  停止服务    ：运行 quit.py")
    print(f"  运行日志    ：{LOG_FILE}")
    print("  再次启动    ：运行 start.py（已完成的步骤会自动跳过）")
    print(f"  数据库      ：PostgreSQL @ 127.0.0.1:{PG_PORT}（密码在 config.json）")


# ───────────────────────────── 主流程 ─────────────────────────────

def preflight() -> None:
    for f in ("go.mod", "cmd/wsartex/main.go", "web/package.json"):
        if not (PROJECT / f).exists():
            die(f"缺少 {f} —— 请确认 start.py 位于项目根目录。",
                "把整个项目文件夹完整下载/解压后再运行本脚本。")


def main() -> None:
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass
    _enable_color()

    print()
    ui_title("WSARTEX 启动器")
    ui_info(f"项目目录：{PROJECT}")

    # ── 1. 识别操作系统 ──
    ui_step(1, "识别操作系统")
    os_kind, os_name = detect_os()
    if os_kind == "unknown":
        die(f"无法识别的操作系统：{os_name}", "本脚本支持 macOS / Linux / Windows。")
    ui_ok(f"当前系统：{os_name}（{os_kind}）")
    preflight()

    # ── 2. 检测依赖 ──
    ui_step(2, "检测外部依赖")
    missing, present = check_deps()
    print_dep_report(missing, present)

    missing_required = [m for m in missing if m[2]]

    if missing_required:
        choice = ask_choice(
            "检测到缺少必需的依赖，请选择：",
            ["退出运行，我自己手动安装依赖", "自动安装目前所需的依赖"],
        )
        if choice == 1:
            ui_info("已退出。安装完依赖后重新运行 start.py 即可。")
            pause_if_double_clicked()
            sys.exit(0)

        if not install_deps(os_kind):
            pause_if_double_clicked()
            sys.exit(1)

        # 安装后重新检测：新装的可执行文件可能尚未进入当前进程的 PATH
        ui_info("重新检测依赖…")
        missing2, present2 = check_deps()
        still = [m for m in missing2 if m[2]]
        if still:
            ui_fail("以下依赖仍未就绪：" + "、".join(m[1] for m in still))
            print("  多数情况是刚安装的工具尚未进入当前终端的 PATH。")
            print("  请关闭本窗口、重新打开后再次运行 start.py。")
            pause_if_double_clicked()
            sys.exit(1)
        print()
        ui_ok("所需依赖已完备")

        choice = ask_choice("依赖已装好，接下来：", ["退出运行", "启动 WSARTEX"])
        if choice == 1:
            ui_info("已退出。下次运行 start.py 即可直接启动。")
            pause_if_double_clicked()
            sys.exit(0)
    else:
        print()
        ui_ok("所需依赖已完备")

    # 必需依赖齐全时，若还有可选工具缺失，单独问一次（不阻断启动）
    if not missing_required:
        missing_optional = [m for m in missing if not m[2]]
        if missing_optional:
            names = "、".join(m[1].replace("（可选）", "") for m in missing_optional)
            choice = ask_choice(
                f"检测到缺少可选的增强工具（{names}），是否安装？",
                ["跳过，直接启动 WSARTEX", "安装后启动"],
            )
            if choice == 2:
                install_optional(os_kind)

    # ── 3. 启动 ──
    created_pw = step_postgres(os_kind)
    step_config(created_pw)
    step_frontend()
    step_backend()
    step_start()
    step_open()

    print()
    ui_ok("全部完成")
    pause_if_double_clicked()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        for tmp in (PROJECT / (BIN_NAME + ".new"),):
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
        print("\n已中断。重新运行 start.py 可继续（已完成的步骤会自动跳过）。")
        sys.exit(130)
