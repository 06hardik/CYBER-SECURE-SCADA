"""
unprotected_receiver.py — Computer B demo listener

Receives a payload over TCP:9999, stores it as dropped_payload.py,
and executes it directly (no Frida / no ML guard).
"""

import os
import socket
import subprocess
import sys


DROP_NAME = "dropped_payload.py"


def receive_payload(port: int = 9999) -> str:
    """Receive a Python payload over TCP and save it as dropped_payload.py."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dropped_path = os.path.join(base_dir, DROP_NAME)

    print(f"[unprotected] Waiting for payload on 0.0.0.0:{port} ...")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", port))
        server.listen(1)

        conn, addr = server.accept()
        with conn:
            print(f"[unprotected] Connection from {addr[0]}:{addr[1]}")
            with open(dropped_path, "wb") as fh:
                while True:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    fh.write(chunk)

    if not os.path.isfile(dropped_path) or os.path.getsize(dropped_path) == 0:
        raise RuntimeError("Received empty payload")

    print(f"[unprotected] Payload saved to: {dropped_path}")
    return dropped_path


def run_payload(path: str) -> int:
    print(f"[unprotected] Executing directly: {path}")
    completed = subprocess.run([sys.executable, path], check=False)
    return completed.returncode


def main() -> None:
    payload_path = receive_payload(port=9999)
    code = run_payload(payload_path)
    print(f"[unprotected] Payload exit code: {code}")


if __name__ == "__main__":
    main()
