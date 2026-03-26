"""
simulator.py — Safe SCADA File Access Simulator
------------------------------------------------
Phase 1: Opens and reads every file in SCADA_ROOT (triggers CreateFile hooks)
Phase 2: Writes a simulated alert to a TEMP file (triggers WriteFile + MALICIOUS verdict)

Completely non-destructive — SCADA_ROOT files are never modified.
"""

import os
import sys
import time
import tempfile

# ── CONFIG ── change this if your SCADA_ROOT is elsewhere ─────────────────────
SCADA_ROOT = r"C:\SCADA_ROOT" if sys.platform == "win32" else "./scada_root"
TEMP_WRITE_TARGET = os.path.join(tempfile.gettempdir(), "sim_write_log.txt")
# ─────────────────────────────────────────────────────────────────────────────

def simulate_reads():
    print("=" * 60)
    print("  SCADA Simulator  |  NON-DESTRUCTIVE MODE")
    print("=" * 60)
    print(f"  SCADA_ROOT : {SCADA_ROOT}")
    print(f"  Write log  : {TEMP_WRITE_TARGET}")
    print("=" * 60)

    if not os.path.isdir(SCADA_ROOT):
        print(f"[SIM] ERROR: {SCADA_ROOT} not found")
        return 0

    count = 0
    for filename in os.listdir(SCADA_ROOT):
        filepath = os.path.join(SCADA_ROOT, filename)
        if not os.path.isfile(filepath):
            continue
        try:
            # Open with explicit read — triggers CreateFileA/W in kernel
            with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
                data = fh.read()
            print(f"[SIM] READ  {filepath}  ({len(data.encode())} bytes)")
            count += 1
        except PermissionError:
            print(f"[SIM] DENIED  {filepath}")
        time.sleep(0.2)

    print(f"\n[SIM] Read phase complete — {count} file(s) accessed.\n")
    return count

def simulate_write():
    """
    Writes to a TEMP file — this triggers WriteFile hook.
    The LLM should flag writes to Temp as MALICIOUS in this SCADA context.
    SCADA_ROOT is never touched.
    """
    payload = (
        f"[SIMULATED WRITE ATTEMPT]\n"
        f"Target directory : {SCADA_ROOT}\n"
        f"Timestamp        : {time.strftime('%Y-%m-%dT%H:%M:%S')}\n"
        f"Note             : Unauthorized write attempt simulation.\n"
    )
    with open(TEMP_WRITE_TARGET, "a", encoding="utf-8") as fh:
        fh.write(payload + "\n")

    print(f"[SIM] WRITE-SIM → {TEMP_WRITE_TARGET}  ({len(payload)} bytes)")
    print(f"[SIM] Write-simulation complete.\n")
    print("[SIM] Simulator finished. SCADA_ROOT was NOT modified.")

def main():
    simulate_reads()
    time.sleep(0.3)
    simulate_write()

if __name__ == "__main__":
    main()
