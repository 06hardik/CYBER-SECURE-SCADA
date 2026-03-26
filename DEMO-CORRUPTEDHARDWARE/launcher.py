"""
launcher.py — Minimal attacker sender

Sends the same payload to both demo targets:
    - Computer B (unprotected): 192.168.10.2
    - Computer C (protected):   192.168.10.3

Usage:
    python launcher.py --file demo_payload.py
    python launcher.py --file demo_payload.py --targets 192.168.10.2,192.168.10.3
    python launcher.py --file demo_payload.py --host 192.168.10.3
"""

import argparse
import os
import socket


DEFAULT_TARGETS = ["192.168.10.2", "192.168.10.3"]


def send_file(file_path: str, host: str, port: int = 9999) -> None:
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "rb") as f:
        payload = f.read()

    with socket.create_connection((host, port), timeout=10) as sock:
        sock.sendall(payload)

    print(f"[launcher] Sent {len(payload)} bytes from {file_path} to {host}:{port}")


def parse_targets(host: str | None, targets: str | None) -> list[str]:
    if host:
        return [host]
    if targets:
        return [x.strip() for x in targets.split(",") if x.strip()]
    return DEFAULT_TARGETS


def main() -> None:
    parser = argparse.ArgumentParser(description="Send payload file to demo targets")
    parser.add_argument("--file", "-f", required=True, help="Path to payload file")
    parser.add_argument("--host", default=None, help="Single target host IP")
    parser.add_argument(
        "--targets",
        default=None,
        help="Comma-separated target IPs (default: 192.168.10.2,192.168.10.3)",
    )
    parser.add_argument("--port", type=int, default=9999, help="Defender port (default: 9999)")
    args = parser.parse_args()

    targets = parse_targets(args.host, args.targets)
    if not targets:
        raise ValueError("No targets specified")

    for ip in targets:
        try:
            send_file(args.file, ip, args.port)
        except Exception as exc:
            print(f"[launcher] Failed to send to {ip}:{args.port} -> {exc}")


if __name__ == "__main__":
    main()
