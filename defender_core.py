"""
defender_core.py — SCADA Behavioral Defense Orchestrator
---------------------------------------------------------
Spawns simulator.py via `python.exe` using Frida (not a compiled exe).
This ensures file I/O goes through hookable DLLs (ucrtbase, ntdll).

Usage:
  python defender_core.py
  python defender_core.py --python C:\\Python313\\python.exe
  python defender_core.py --script path\\to\\simulator.py

Requirements:
  pip install frida==16.5.9 rich
  ollama serve  +  ollama pull phi3:mini
"""

import os
import sys
import time
import signal
import argparse
import threading

import frida
from scada_guard import classify

try:
    from rich.console import Console
    from rich.panel   import Panel
    console  = Console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

# ── CONFIG ────────────────────────────────────────────────────────────────────
DEFAULT_PYTHON  = r"C:\Python313\python.exe"   # ← adjust if Python is elsewhere
DEFAULT_SCRIPT  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "simulator.py")
HOOK_SCRIPT     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hook.js")
LOG_DIR         = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
LOG_FILE        = os.path.join(LOG_DIR, "events.log")
# ─────────────────────────────────────────────────────────────────────────────


def _log(line: str):
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def banner(python_exe, script):
    if HAS_RICH:
        console.print(Panel.fit(
            "[bold cyan]SCADA Behavioral Defense System[/]\n"
            "[dim]Frida + LLM real-time intercept[/]",
            border_style="cyan"
        ))
        console.print(f"\n[dim]Python :[/] [white]{python_exe}[/]")
        console.print(f"[dim]Script :[/] [white]{script}[/]")
        console.print(f"[dim]Hooks  :[/] [white]{HOOK_SCRIPT}[/]")
        console.print(f"[dim]Log    :[/] [white]{LOG_FILE}[/]\n")
    else:
        print("=" * 58)
        print("  SCADA Behavioral Defense System")
        print("=" * 58)
        print(f"  Python : {python_exe}")
        print(f"  Script : {script}")
        print(f"  Hooks  : {HOOK_SCRIPT}")
        print(f"  Log    : {LOG_FILE}\n")


def show_event(ev: dict):
    ts   = time.strftime("%H:%M:%S")
    hook = ev.get("hook", "?")
    path = ev.get("path", "?")
    byt  = ev.get("bytes", 0)
    rw   = "WRITE" if ev.get("is_write") else "READ"
    line = f"[{ts}] INTERCEPTED  {hook:14s}  {rw:5s}  {byt:6d}B  →  {path}"
    if HAS_RICH:
        console.print(
            f"[yellow][{ts}][/] [cyan]INTERCEPTED[/]  "
            f"[white]{hook:14s}[/]  [magenta]{rw:5s}[/]  "
            f"[dim]{byt:6d}B[/]  → [white]{path}[/]"
        )
    else:
        print(line)
    _log(line)


def show_verdict(verdict: str, action: str):
    vc = "red"      if verdict == "MALICIOUS" else "green"
    ac = "bold red" if action  == "KILLED"    else "bold green"
    if HAS_RICH:
        console.print(
            f"         [bold]LLM[/] → [{vc}]{verdict}[/]"
            f"   [bold]ACTION[/] → [{ac}]{action}[/]\n"
        )
    else:
        print(f"         LLM → {verdict}   ACTION → {action}\n")
    _log(f"         LLM={verdict}  ACTION={action}")


class Defender:
    def __init__(self, python_exe: str, script_path: str):
        self.python_exe  = python_exe
        self.script_path = script_path
        self.pid         = None
        self.session     = None
        self.script      = None
        self._done       = threading.Event()

    def _hook_src(self) -> str:
        if not os.path.isfile(HOOK_SCRIPT):
            raise FileNotFoundError(f"hook.js missing: {HOOK_SCRIPT}")
        with open(HOOK_SCRIPT, "r", encoding="utf-8") as f:
            return f.read()

    def _on_message(self, message: dict, _data):
        if message.get("type") == "error":
            desc  = message.get("description", "")
            stack = message.get("stack", "")
            txt   = f"[hook.js ERROR] {desc}"
            if stack:
                txt += f"\n  {stack.splitlines()[0]}"
            if HAS_RICH:
                console.print(f"[red]{txt}[/]")
            else:
                print(txt)
            _log(txt)
            return

        if message.get("type") != "send":
            return

        payload  = message["payload"]
        event_id = payload.get("event_id", "")
        hook     = payload.get("hook", "")
        path     = payload.get("path", "")
        byt      = payload.get("bytes", 0)
        is_write = payload.get("is_write", False)

        show_event(payload)
        verdict = classify(hook, path, byt, is_write)

        if verdict == "MALICIOUS":
            show_verdict("MALICIOUS", "KILLED")
            if self.script:
                try:
                    self.script.post({"type": event_id, "payload": "kill"})
                except Exception:
                    pass
            time.sleep(0.1)
            self._kill()
            self._done.set()
        else:
            show_verdict("BENIGN", "RESUMED")
            if self.script:
                try:
                    self.script.post({"type": event_id, "payload": "resume"})
                except Exception as e:
                    print(f"[defender] post failed: {e}")

    def _kill(self):
        if self.pid is not None and not getattr(self, "_killed", False):
            self._killed = True
            try:
                frida.kill(self.pid)
                msg = f"  ✖  Process {self.pid} terminated by defender."
                if HAS_RICH:
                    console.print(f"[bold red]{msg}[/]\n")
                else:
                    print(msg)
            except Exception as e:
                print(f"[defender] kill failed: {e}")

    def run(self):
        banner(self.python_exe, self.script_path)

        # Validate paths
        if not os.path.isfile(self.python_exe):
            print(f"[ERROR] Python not found: {self.python_exe}")
            print("  Set the correct path with --python")
            sys.exit(1)
        if not os.path.isfile(self.script_path):
            print(f"[ERROR] Simulator script not found: {self.script_path}")
            sys.exit(1)

        if HAS_RICH:
            console.print("[cyan]→[/] Spawning python.exe + simulator.py (suspended)…")
        else:
            print("→ Spawning python.exe + simulator.py (suspended)…")

        # Spawn python.exe with simulator.py as argument — SUSPENDED
        # This is the key change: we spawn the real python.exe, not a frozen exe
        self.pid = frida.spawn(
            self.python_exe,
            argv=[self.python_exe, self.script_path],
            stdio="pipe"
        )

        self.session = frida.attach(self.pid)
        self.script  = self.session.create_script(self._hook_src())
        self.script.on("message", self._on_message)
        self.script.load()

        if HAS_RICH:
            console.print("[cyan]→[/] Hooks injected. Resuming…\n")
        else:
            print("→ Hooks injected. Resuming…\n")

        frida.resume(self.pid)

        try:
            self._done.wait(timeout=120)
        except KeyboardInterrupt:
            print("\n[defender] Interrupted.")
            self._kill()
        finally:
            try:
                self.session.detach()
            except Exception:
                pass

        if HAS_RICH:
            console.print("\n[bold green]  ✔  Defender session complete.[/]")
        else:
            print("\n  ✔  Defender session complete.")
        print(f"  Log: {LOG_FILE}\n")


def main():
    ap = argparse.ArgumentParser(description="SCADA Behavioral Defender")
    ap.add_argument("--python", "-p", default=DEFAULT_PYTHON,
                    help=f"Path to python.exe (default: {DEFAULT_PYTHON})")
    ap.add_argument("--script", "-s", default=DEFAULT_SCRIPT,
                    help=f"Path to simulator.py (default: {DEFAULT_SCRIPT})")
    args = ap.parse_args()

    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    Defender(python_exe=args.python, script_path=args.script).run()


if __name__ == "__main__":
    main()
