#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WSARTEX 退出脚本（跨平台：macOS / Linux / Windows）
===================================================

用法：双击本文件，或在项目根目录执行 `python3 quit.py`

作用：结束所有与 WSARTEX 相关的进程（后端服务及其守护进程），并确认管理端口已释放。
     数据库 PostgreSQL 是独立的系统服务，本脚本**不会**停止它；如需一并停用，
     脚本结束时会打印对应命令。
"""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT = Path(__file__).resolve().parent
DATA_DIR = PROJECT / "data"
PID_FILE = DATA_DIR / "wsartex-launcher.pid"
BIN_NAME = "wsartex.exe" if os.name == "nt" else "wsartex"

ADDR = "127.0.0.1:8787"
PORT = 8787
HEALTH_URL = f"http://{ADDR}/api/health"

IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")
IS_WIN = os.name == "nt"

C_OK, C_BAD, C_WARN, C_TITLE, C_BOLD, C_END = (
    "\033[32m", "\033[31m", "\033[33m", "\033[1;36m", "\033[1m", "\033[0m",
)


def _enable_color() -> None:
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
def ui_title(t: str) -> None: print(f"\n{C_TITLE}{t}{C_END}")


def pause_if_double_clicked() -> None:
    if sys.stdin is not None and sys.stdin.isatty():
        try:
            input("\n按回车键结束…")
        except (EOFError, KeyboardInterrupt):
            pass


def run(cmd: List[str], timeout: int = 60) -> Tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "").strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return 127, ""


def health_ok() -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=3) as r:
            data = json.loads(r.read().decode("utf-8"))
        return data.get("service") == "wsartex"
    except (urllib.error.URLError, OSError, ValueError):
        return False


def port_listening() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if IS_WIN:
        rc, out = run(["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"])
        return rc == 0 and str(pid) in out
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False


def matching_processes() -> List[Tuple[int, str]]:
    """找出命令行里同时含本项目路径与 wsartex 后端/守护脚本的进程；排除本脚本自身。"""
    me = os.getpid()
    proj = str(PROJECT)
    found: List[Tuple[int, str]] = []

    if IS_WIN:
        rc, txt = run(["powershell", "-NoProfile", "-Command",
                       "Get-CimInstance Win32_Process | "
                       "ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }"], timeout=90)
        if rc != 0:
            return found
        for line in txt.splitlines():
            if "\t" not in line:
                continue
            pid_s, _, cmdline = line.partition("\t")
            if not pid_s.strip().isdigit():
                continue
            pid = int(pid_s.strip())
            if pid == me or not cmdline:
                continue
            low = cmdline.lower()
            if "python" in low or "quit.py" in low or "start.py" in low:
                continue
            if BIN_NAME.lower() in low and proj.lower().replace("/", "\\") in low.replace("/", "\\"):
                found.append((pid, cmdline.strip()))
        return found

    rc, txt = run(["ps", "-eo", "pid=,command="], timeout=30)
    if rc != 0:
        return found
    for line in txt.splitlines():
        line = line.strip()
        if not line:
            continue
        pid_s, _, cmdline = line.partition(" ")
        if not pid_s.isdigit():
            continue
        pid = int(pid_s)
        if pid == me:
            continue
        if "quit.py" in cmdline or "start.py" in cmdline:
            continue
        # 只认后端本体，避免误伤同目录下的其它命令。命令行有两种写法：
        #   · 绝对路径（start.py 拉起的形态）——要求同时含项目路径；
        #   · 相对路径 `./wsartex …` / `wsartex …`（手工在项目根执行）——这种写法里
        #     没有项目绝对路径，只按二进制名判断（本项目是本地单实例工具，够用）。
        if f"{os.sep}wsartex" in cmdline and proj in cmdline:
            found.append((pid, cmdline.strip()))
        elif cmdline.startswith(("./wsartex", "wsartex ", "wsartex.exe")):
            found.append((pid, cmdline.strip()))
    return found


def terminate(pid: int, force: bool = False) -> bool:
    if IS_WIN:
        args = ["taskkill", "/PID", str(pid), "/T"] + (["/F"] if force else [])
        rc, _ = run(args)
        return rc == 0
    try:
        os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def main() -> int:
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass
    _enable_color()

    print()
    ui_title("WSARTEX 退出")

    running = health_ok()
    procs = matching_processes()
    pid_from_file: Optional[int] = None
    if PID_FILE.exists():
        try:
            raw = PID_FILE.read_text().strip()
            pid_from_file = int(raw) if raw.isdigit() else None
        except OSError:
            pid_from_file = None

    if not running and not procs and not (pid_from_file and pid_alive(pid_from_file)):
        ui_ok("WSARTEX 当前未在运行，无需操作")
        if PID_FILE.exists():
            try:
                PID_FILE.unlink()
            except OSError:
                pass
        print("  （数据库 PostgreSQL 是独立服务，未受影响）")
        pause_if_double_clicked()
        return 0

    # 先按 PID 文件优雅停止守护脚本，它会转发信号给后端做优雅关闭
    targets: List[Tuple[int, str]] = []
    if pid_from_file and pid_alive(pid_from_file):
        targets.append((pid_from_file, "（来自 PID 文件的守护进程）"))
    for pid, cmd in procs:
        if all(pid != t[0] for t in targets):
            targets.append((pid, cmd))

    ui_info(f"找到 {len(targets)} 个相关进程：")
    for pid, cmd in targets:
        print(f"    · PID {pid}  {cmd[:90]}")

    print()
    ui_info("发送停止信号（优雅关闭，最多等待 15 秒）…")
    for pid, _ in targets:
        terminate(pid, force=False)

    # 等到「端口已释放」且「相关进程都已退出」才算优雅关闭完成：
    # 只看端口会在守护脚本还没来得及退出的瞬间就误判为需要强杀。
    deadline = time.time() + 15
    while time.time() < deadline:
        if not health_ok() and not port_listening() and not any(pid_alive(p) for p, _ in targets):
            break
        time.sleep(0.5)
    else:
        ui_warn("优雅关闭超时，强制结束残留进程…")
        for pid, _ in targets:
            if pid_alive(pid):
                terminate(pid, force=True)
        time.sleep(1.5)

    # 端口仍被占用时，做一次兜底扫描
    if port_listening():
        extra = [(pid, cmd) for pid, cmd in matching_processes()
                 if all(pid != t[0] for t in targets)]
        for pid, cmd in extra:
            ui_warn(f"强制结束残留进程 PID {pid}  {cmd[:70]}")
            terminate(pid, force=True)
        time.sleep(1.5)

    if PID_FILE.exists():
        try:
            PID_FILE.unlink()
        except OSError:
            pass

    print()
    if health_ok() or port_listening():
        ui_fail(f"端口 {PORT} 仍被占用，可能被非本项目的程序占用。")
        if IS_WIN:
            print(f"  排查：netstat -ano | findstr {PORT}")
        else:
            print(f"  排查：lsof -nP -iTCP:{PORT} -sTCP:LISTEN")
        print("  确认该进程不是 WSARTEX 后，可用系统方式结束它。")
        pause_if_double_clicked()
        return 1

    ui_ok("WSARTEX 已停止，端口已释放")
    print()
    ui_title("★ 说明")
    print("  · 数据库 PostgreSQL 是独立的系统服务，本次未停止；如需停用：")
    if IS_MAC:
        print("      brew services stop postgresql@16")
    elif IS_WIN:
        print("      net stop postgresql-x64-16   （服务名以实际安装为准）")
    else:
        print("      sudo systemctl stop postgresql")
    print("  · 数据（任务、资产、漏洞、流量）都保存在数据库与 data/ 目录中，停止服务不会丢失。")
    print("  · 重新启动：运行 start.py")
    pause_if_double_clicked()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已取消。")
        sys.exit(130)
