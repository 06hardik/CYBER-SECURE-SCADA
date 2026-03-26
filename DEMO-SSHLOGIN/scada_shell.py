import argparse
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime

import serial
import torch

from Sovereign_SCADA_AI.model import MicroTransformer
from Sovereign_SCADA_AI.tokenizer import SCADATokenizer

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    HAS_RICH = True
    console = Console()
except ImportError:
    HAS_RICH = False
    console = None

# --- CONFIGURATION ---
ARDUINO_PORT = "COM8"
BAUD_RATE = 9600
SECONDARY_PIN = "9988"
SERVER_PORT = 10051

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Sovereign_SCADA_AI")
MODEL_PATH = os.path.join(MODEL_DIR, "scada_model.pth")
VOCAB_PATH = os.path.join(MODEL_DIR, "vocab.json")

KNOWN_USERS = {"admin_01", "operator_02", "guest_user", "maintenance_bot"}
KNOWN_ACTIONS = {"read_temp", "check_valve", "status_ping", "write_firmware", "emergency_stop"}
KNOWN_TARGETS = {"turbine_A", "boiler_04", "plc_controller", "grid_switch"}
ACTION_CANON = {a.lower(): a for a in KNOWN_ACTIONS}
TARGET_CANON = {t.lower(): t for t in KNOWN_TARGETS}

SCADA_ALIASES = {
    "grid off": ("write_firmware", "grid_switch"),
    "turn off turbine": ("write_firmware", "grid_switch"),
    "turn off device": ("write_firmware", "grid_switch"),
    "shutdown": ("write_firmware", "grid_switch"),
    "poweroff": ("write_firmware", "grid_switch"),
    "grid on": ("status_ping", "grid_switch"),
    "turn on turbine": ("status_ping", "grid_switch"),
    "turn on device": ("status_ping", "grid_switch"),
}

SERIAL_BACKEND_OK = hasattr(serial, "Serial")


def _print_header(title: str, subtitle: str):
    if HAS_RICH:
        console.print(Panel.fit(
            f"[bold cyan]{title}[/]\n[dim]{subtitle}[/]",
            border_style="cyan"
        ))
    else:
        print("=" * 62)
        print(f" {title}")
        print(f" {subtitle}")
        print("=" * 62)


def _print_info(line: str):
    if HAS_RICH:
        console.print(f"[cyan]{line}[/]")
    else:
        print(line)


def _print_warn(line: str):
    if HAS_RICH:
        console.print(f"[yellow]{line}[/]")
    else:
        print(line)


def _print_error(line: str):
    if HAS_RICH:
        console.print(f"[bold red]{line}[/]")
    else:
        print(line)


def _print_success(line: str):
    if HAS_RICH:
        console.print(f"[bold green]{line}[/]")
    else:
        print(line)


def _print_ai_eval(command: str, scada_log: str | None, score: float | None, verdict: str):
    ts = datetime.now().strftime("%H:%M:%S")
    if HAS_RICH:
        table = Table(show_header=False, box=None, pad_edge=False)
        table.add_row("[dim]Time[/]", f"[white]{ts}[/]")
        table.add_row("[dim]Command[/]", f"[white]{command}[/]")
        table.add_row("[dim]Mapped Log[/]", f"[white]{scada_log or 'N/A'}[/]")
        table.add_row("[dim]Score[/]", f"[white]{'N/A' if score is None else f'{score:.4f}'}[/]")
        verdict_style = "bold red" if verdict == "ANOMALY" else "bold green"
        table.add_row("[dim]Verdict[/]", f"[{verdict_style}]{verdict}[/]")
        console.print(Panel(table, border_style="bright_blue", title="AI Inspection"))
    else:
        score_txt = "N/A" if score is None else f"{score:.4f}"
        print(f"[AI] t={ts} cmd={command} | log={scada_log or 'N/A'} | score={score_txt} | verdict={verdict}")


def _print_hold_notice(command: str):
    if HAS_RICH:
        console.print(Panel.fit(
            "[bold red]MALICIOUS COMMAND DETECTED[/]\n"
            f"[yellow]Command on hold:[/] [white]{command}[/]\n"
            "[yellow]Execution paused. Awaiting supervisor approval.[/]",
            border_style="red",
            title="Threat Intercept"
        ))
    else:
        print("\n[!] MICRO-TRANSFORMER ALERT: Anomalous Context Detected [!]")
        print(f"[!] Command on hold: {command}")
        print("[!] Execution paused. Awaiting supervisor approval.\n")


def _current_scada_user(default_user: str = "guest_user") -> str:
    user = os.getenv("SCADA_USER", default_user)
    return user if user in KNOWN_USERS else "guest_user"


def _to_scada_log(command: str, user: str):
    cmd = command.strip()
    if not cmd:
        return None

    hour = time.localtime().tm_hour
    cmd_lower = cmd.lower()

    if cmd_lower in SCADA_ALIASES:
        action, target = SCADA_ALIASES[cmd_lower]
        return f"[{hour:02d}:00] USER: {user} ACTION: {action} TARGET: {target}"

    parts = cmd.split()
    if len(parts) == 2:
        action = ACTION_CANON.get(parts[0].lower())
        target = TARGET_CANON.get(parts[1].lower())
        if action and target:
            return f"[{hour:02d}:00] USER: {user} ACTION: {action} TARGET: {target}"

    if "USER:" in cmd and "ACTION:" in cmd and "TARGET:" in cmd:
        return cmd

    return None


def _extract_scada_action_target(command: str):
    cmd = command.strip()
    if not cmd:
        return None

    cmd_lower = cmd.lower()
    if cmd_lower in SCADA_ALIASES:
        return SCADA_ALIASES[cmd_lower]

    parts = cmd.split()
    if len(parts) == 2:
        action = ACTION_CANON.get(parts[0].lower())
        target = TARGET_CANON.get(parts[1].lower())
        if action and target:
            return (action, target)

    return None


def _partial_scada_error(command: str):
    cmd = command.strip()
    if not cmd:
        return None

    parts = cmd.split()
    head = parts[0].lower()

    if head in ACTION_CANON and len(parts) == 1:
        return "Incomplete SCADA command: missing <target>. Example: read_temp turbine_A"

    if head == "grid" and len(parts) == 1:
        return "Incomplete alias: use 'grid on' or 'grid off'."

    return None


def _load_transformer_artifacts():
    tokenizer = SCADATokenizer()
    with open(VOCAB_PATH, "r", encoding="utf-8") as f:
        tokenizer.vocab = json.load(f)

    model = MicroTransformer(vocab_size=len(tokenizer.vocab))
    state = torch.load(MODEL_PATH, map_location="cpu")
    model.load_state_dict(state)
    model.eval()
    return tokenizer, model


try:
    TOKENIZER, MODEL = _load_transformer_artifacts()
    MODEL_READY = True
except Exception as e:
    _print_error(f"AI Model Error: {e}")
    _print_warn("Falling back to conservative keyword defense mode.")
    TOKENIZER, MODEL = None, None
    MODEL_READY = False


def analyze_command_with_transformer(command: str, user: str):
    scada_log = _to_scada_log(command, user=user)

    if MODEL_READY and scada_log is not None:
        encoded = torch.tensor([TOKENIZER.encode(scada_log)])
        with torch.no_grad():
            score = MODEL(encoded).item()
        verdict = "ANOMALY" if score > 0.5 else "SAFE"
        return verdict, scada_log, score

    command_lower = command.lower()
    if any(k in command_lower for k in ("grid off", "shutdown", "poweroff", "write_firmware")):
        return "ANOMALY", scada_log, None
    return "SAFE", scada_log, None


def _json_send(sock: socket.socket, payload: dict):
    wire = (json.dumps(payload) + "\n").encode("utf-8")
    sock.sendall(wire)


def _json_recv_line(buffer: bytearray, sock: socket.socket):
    while True:
        pos = buffer.find(b"\n")
        if pos != -1:
            line = bytes(buffer[:pos])
            del buffer[:pos + 1]
            return json.loads(line.decode("utf-8"))
        chunk = sock.recv(4096)
        if not chunk:
            return None
        buffer.extend(chunk)


def _execute_command(command: str, grid_controller):
    scada_cmd = _extract_scada_action_target(command)
    if scada_cmd:
        action, target = scada_cmd
        result = f"[SCADA] Executed: ACTION={action} TARGET={target}"

        # Hardware trigger path for demo grid control
        if action == "write_firmware" and target == "grid_switch":
            if grid_controller:
                try:
                    grid_controller.write(b"0")
                    grid_controller.flush()
                    _print_success("[HW] Signal sent to Arduino: grid OFF (0)")
                except Exception as e:
                    _print_error(f"[HW] Failed to send OFF signal: {e}")
            else:
                _print_warn("[HW] Arduino not connected. OFF signal skipped.")
        elif action == "status_ping" and target == "grid_switch":
            if grid_controller:
                try:
                    grid_controller.write(b"1")
                    grid_controller.flush()
                    _print_success("[HW] Signal sent to Arduino: grid ON (1)")
                except Exception as e:
                    _print_error(f"[HW] Failed to send ON signal: {e}")
            else:
                _print_warn("[HW] Arduino not connected. ON signal skipped.")

        return result, ""

    try:
        proc = subprocess.run(command, shell=True, text=True, capture_output=True)
        return proc.stdout or "", proc.stderr or ""
    except Exception as e:
        return "", f"Execution Error: {e}"


def _connect_arduino():
    if not SERIAL_BACKEND_OK:
        _print_error("Python package conflict: imported 'serial' package is not pyserial.")
        _print_warn("Fix: pip uninstall serial ; pip install pyserial")
        _print_warn("Running in software-only mode for debugging.")
        return None

    try:
        grid = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)
        _print_success(f"Arduino connected on {ARDUINO_PORT} @ {BAUD_RATE} baud.")
        return grid
    except Exception as e:
        _print_warn(f"Hardware Error: Could not connect to Arduino on {ARDUINO_PORT}: {e}")
        _print_warn("Running in software-only mode for debugging.")
        return None


def run_server(host: str, port: int):
    _print_header("Sovereign SCADA Defense Console", "Computer C | Approval + AI Inspection")
    _print_info(f"Supervisor PIN configured: {SECONDARY_PIN}")
    _print_info(f"Listening on {host}:{port}\n")

    grid_controller = _connect_arduino()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(1)

        while True:
            conn, addr = server.accept()
            with conn:
                _print_success(f"Client connected: {addr[0]}:{addr[1]}")
                buffer = bytearray()
                while True:
                    msg = _json_recv_line(buffer, conn)
                    if msg is None:
                        _print_warn("Client disconnected.\n")
                        break
                    if msg.get("type") != "command":
                        continue

                    cmd = msg.get("command", "")
                    actor = msg.get("actor", _current_scada_user())

                    partial_err = _partial_scada_error(cmd)
                    if partial_err:
                        _json_send(conn, {
                            "type": "result",
                            "status": "rejected",
                            "message": partial_err,
                        })
                        continue

                    verdict, ai_log, score = analyze_command_with_transformer(cmd, user=actor)
                    _print_ai_eval(cmd, ai_log, score, verdict)

                    if verdict == "ANOMALY":
                        _print_hold_notice(cmd)
                        _json_send(conn, {
                            "type": "result",
                            "status": "hold",
                            "message": "Command is on hold for supervisor approval.",
                        })

                        auth_attempt = input("[Computer C] Enter Supervisor PIN to release or reject: ")
                        if auth_attempt != SECONDARY_PIN:
                            _print_error("Verification FAILED. Command rejected.\n")
                            _json_send(conn, {
                                "type": "result",
                                "status": "rejected",
                                "message": "Supervisor rejected command.",
                            })
                            continue

                        _print_success("Verification SUCCESS. Releasing command from hold.\n")
                        out, err = _execute_command(cmd, grid_controller)
                        _json_send(conn, {
                            "type": "result",
                            "status": "approved",
                            "stdout": out,
                            "stderr": err,
                            "message": "Supervisor approved and command executed.",
                        })
                        continue

                    out, err = _execute_command(cmd, grid_controller)
                    _json_send(conn, {
                        "type": "result",
                        "status": "ok",
                        "stdout": out,
                        "stderr": err,
                        "message": "Command executed.",
                    })


def run_baseline_server(host: str, port: int):
    # Computer B network endpoint: direct execution, no AI inspection or approval.
    _print_header("SCADA Baseline Service", "Computer B | Unprotected network endpoint")
    _print_warn("AI inspection and supervisor approval are DISABLED in this mode.")
    _print_info(f"Listening on {host}:{port}\n")

    grid_controller = _connect_arduino()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(1)

        while True:
            conn, addr = server.accept()
            with conn:
                _print_success(f"Client connected: {addr[0]}:{addr[1]}")
                buffer = bytearray()
                while True:
                    msg = _json_recv_line(buffer, conn)
                    if msg is None:
                        _print_warn("Client disconnected.\n")
                        break
                    if msg.get("type") != "command":
                        continue

                    cmd = msg.get("command", "")
                    partial_err = _partial_scada_error(cmd)
                    if partial_err:
                        _json_send(conn, {
                            "type": "result",
                            "status": "rejected",
                            "message": partial_err,
                        })
                        continue

                    out, err = _execute_command(cmd, grid_controller)
                    _json_send(conn, {
                        "type": "result",
                        "status": "ok",
                        "stdout": out,
                        "stderr": err,
                        "message": "Command executed on unprotected node.",
                    })


def run_client(host: str, port: int, actor: str):
    _print_header("SCADA Operator Terminal", "Computer A | Command Console")
    _print_info(f"Connected target: {host}:{port}")
    _print_info("Type 'help' for command grammar, 'exit' to quit.\n")

    with socket.create_connection((host, port), timeout=30) as sock:
        buffer = bytearray()

        while True:
            cmd = input("attacker@scada-a:~$ ").strip()
            if not cmd:
                continue
            if cmd.lower() == "exit":
                break
            if cmd.lower() == "help":
                print("<action> <target>")
                print("Actions: read_temp, check_valve, status_ping, write_firmware, emergency_stop")
                print("Targets: turbine_A, boiler_04, plc_controller, grid_switch")
                print("Aliases: grid off, grid on, shutdown, poweroff")
                print("")
                continue

            _json_send(sock, {
                "type": "command",
                "actor": actor,
                "command": cmd,
            })

            first = _json_recv_line(buffer, sock)
            if first is None:
                _print_error("Connection closed by Computer C.")
                break

            status = first.get("status")
            if status == "hold":
                _print_warn("[Computer A] Command in wait for approval on Computer C...")
                final = _json_recv_line(buffer, sock)
                if final is None:
                    _print_error("Connection closed before approval response.")
                    break
                status = final.get("status")
                if status == "approved":
                    _print_success("[Computer A] Approved by Computer C. Command executed.")
                    if final.get("stdout"):
                        print(final["stdout"], end="")
                    if final.get("stderr"):
                        print(final["stderr"], end="", file=sys.stderr)
                else:
                    _print_error(f"[Computer A] Rejected by Computer C: {final.get('message', 'Rejected')}")
                continue

            if status == "ok":
                if first.get("stdout"):
                    print(first["stdout"], end="")
                if first.get("stderr"):
                    print(first["stderr"], end="", file=sys.stderr)
                continue

            _print_error(f"[Computer A] Command rejected: {first.get('message', 'Rejected')}")


def parse_args():
    ap = argparse.ArgumentParser(description="SCADA dual-terminal shell")
    ap.add_argument("--mode", choices=["c-server", "b-server", "a-client", "local", "b-baseline"], default="local",
                    help="c-server: defended C endpoint, b-server: unprotected B endpoint, a-client: attacker terminal, b-baseline/local: local shells")
    ap.add_argument("--host", default=None, help="Server bind host for c-server, target host for a-client")
    ap.add_argument("--port", type=int, default=SERVER_PORT, help=f"Socket port (default: {SERVER_PORT})")
    ap.add_argument("--actor", default=_current_scada_user(),
                    help="SCADA actor identity for a-client (admin_01/operator_02/guest_user/maintenance_bot)")
    return ap.parse_args()


def run_local():
    # Local mode keeps the previous single-terminal behavior for quick testing.
    actor = _current_scada_user()
    _print_header("Sovereign SCADA Defense Shell", "Local mode | AI + Approval in same terminal")
    _print_info("Type 'help' for SCADA grammar or 'exit' to quit.\n")

    grid_controller = _connect_arduino()

    while True:
        try:
            cmd = input("root@scada-node-C:~# ").strip()
            if not cmd:
                continue
            if cmd.lower() == "exit":
                break
            if cmd.lower() == "help":
                print("SCADA command grammar:")
                print("  <action> <target>")
                print("Actions: read_temp, check_valve, status_ping, write_firmware, emergency_stop")
                print("Targets: turbine_A, boiler_04, plc_controller, grid_switch")
                print("Aliases: grid off, grid on, shutdown, poweroff")
                print("Use env SCADA_USER={admin_01|operator_02|guest_user|maintenance_bot}\n")
                continue

            partial_err = _partial_scada_error(cmd)
            if partial_err:
                _print_warn(f"[SCADA] {partial_err}\n")
                continue

            verdict, ai_log, score = analyze_command_with_transformer(cmd, user=actor)
            _print_ai_eval(cmd, ai_log, score, verdict)

            if verdict == "ANOMALY":
                _print_hold_notice(cmd)
                auth_attempt = input("Enter Supervisor PIN: ")
                if auth_attempt != SECONDARY_PIN:
                    _print_error("Verification FAILED. Command dropped. Incident logged.\n")
                    continue
                _print_success("Verification SUCCESS. Releasing command from hold and executing.\n")

            out, err = _execute_command(cmd, grid_controller)
            if out:
                print(out, end="" if out.endswith("\n") else "\n")
            if err:
                print(err, end="", file=sys.stderr)

        except KeyboardInterrupt:
            print("\nExiting SCADA Shell...")
            break


def run_baseline():
    # Baseline mode represents Computer B: no AI inspection, no approval gate.
    _print_header("SCADA Baseline Terminal", "Computer B | No protection")
    _print_warn("AI inspection and supervisor approval are DISABLED in this mode.")
    _print_info("Type 'help' for SCADA grammar or 'exit' to quit.\n")

    grid_controller = _connect_arduino()

    while True:
        try:
            cmd = input("root@scada-node-B:~# ").strip()
            if not cmd:
                continue
            if cmd.lower() == "exit":
                break
            if cmd.lower() == "help":
                print("SCADA command grammar:")
                print("  <action> <target>")
                print("Actions: read_temp, check_valve, status_ping, write_firmware, emergency_stop")
                print("Targets: turbine_A, boiler_04, plc_controller, grid_switch")
                print("Aliases: grid off, grid on, shutdown, poweroff")
                print("")
                continue

            partial_err = _partial_scada_error(cmd)
            if partial_err:
                _print_warn(f"[SCADA] {partial_err}\n")
                continue

            out, err = _execute_command(cmd, grid_controller)
            if out:
                print(out, end="" if out.endswith("\n") else "\n")
            if err:
                print(err, end="", file=sys.stderr)

        except KeyboardInterrupt:
            print("\nExiting baseline shell...")
            break


def main():
    args = parse_args()
    host = args.host
    if host is None:
        host = "0.0.0.0" if args.mode in ("c-server", "b-server") else "127.0.0.1"

    if args.mode == "c-server":
        run_server(host=host, port=args.port)
    elif args.mode == "b-server":
        run_baseline_server(host=host, port=args.port)
    elif args.mode == "a-client":
        run_client(host=host, port=args.port, actor=args.actor)
    elif args.mode == "b-baseline":
        run_baseline()
    else:
        run_local()


if __name__ == "__main__":
    main()
