"""
launcher.py — Minimal attacker sender

Sends a local file to the defender listener on port 9999.

Usage:
  python launcher.py --file payload.py
  python launcher.py --file payload.py --host 192.168.1.50 --port 9999
"""

import argparse
import os
import socket


def send_file(file_path: str, host: str = "127.0.0.1", port: int = 9999) -> None:
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "rb") as f:
        payload = f.read()

    with socket.create_connection((host, port), timeout=10) as sock:
        sock.sendall(payload)

    print(f"[launcher] Sent {len(payload)} bytes from {file_path} to {host}:{port}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Send payload file to defender")
    parser.add_argument("--file", "-f", required=True, help="Path to payload file")
    parser.add_argument("--host", default="127.0.0.1", help="Defender host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=9999, help="Defender port (default: 9999)")
    args = parser.parse_args()

    send_file(args.file, args.host, args.port)


if __name__ == "__main__":
    main()
