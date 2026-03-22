"""
data_gen.py — Synthetic SCADA Syscall Dataset Generator
---------------------------------------------------------
Generates labeled (event, label) pairs for training.

BENIGN  = 0   (normal read activity)
MALICIOUS = 1 (writes to SCADA/sensitive paths, suspicious patterns)

Output: data/train.jsonl  data/val.jsonl  data/test.jsonl
Run:    python data_gen.py
"""

import json
import random
import os

random.seed(42)

OUT_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(OUT_DIR, exist_ok=True)

# ── Path pools ────────────────────────────────────────────────────────────────

SCADA_FILES = [
    r"C:\SCADA_ROOT\pressure_thresholds.txt",
    r"C:\SCADA_ROOT\turbine_auth.csv",
    r"C:\SCADA_ROOT\grid_config.txt",
    r"C:\SCADA_ROOT\safety_limits.txt",
    r"C:\SCADA_ROOT\plc_config.ini",
    r"C:\SCADA_ROOT\hmi_settings.xml",
    r"C:\SCADA_ROOT\alarm_thresholds.cfg",
    r"C:\SCADA_ROOT\operator_log.txt",
    r"C:\SCADA_ROOT\backup\grid_config.bak",
    r"C:\SCADA_ROOT\backup\safety_limits.bak",
]

SYSTEM_FILES = [
    r"C:\Windows\System32\kernel32.dll",
    r"C:\Windows\System32\ntdll.dll",
    r"C:\Windows\System32\ucrtbase.dll",
    r"C:\Windows\SysWOW64\msvcrt.dll",
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\System32\drivers\etc\hosts",
]

PYTHON_FILES = [
    r"C:\Python313\Lib\os.py",
    r"C:\Python313\Lib\pathlib.py",
    r"C:\Python313\DLLs\python313.dll",
    r"C:\Python313\Lib\site-packages\frida\__init__.py",
    r"C:\Users\LOQ\AppData\Local\Programs\Python\Python313\python.exe",
]

TEMP_FILES = [
    r"C:\Users\LOQ\AppData\Local\Temp\sim_write_log.txt",
    r"C:\Users\LOQ\AppData\Local\Temp\scada_dump.tmp",
    r"C:\Users\LOQ\AppData\Local\Temp\exfil_data.txt",
    r"C:\Users\LOQ\AppData\Local\Temp\_MEI182522\VCRUNTIME140.dll",
    r"C:\Users\LOQ\AppData\Local\Temp\pip-tmp\setup.py",
    r"C:\Temp\payload_out.bin",
    r"C:\Temp\stolen_config.txt",
]

APP_FILES = [
    r"C:\Program Files\MyApp\config.ini",
    r"C:\Program Files\MyApp\data\users.db",
    r"C:\Users\LOQ\Documents\report.docx",
    r"C:\Users\LOQ\Desktop\notes.txt",
    r"D:\Projects\app\settings.json",
]

HOOKS = ["CreateFileW", "CreateFileA", "NtCreateFile", "WriteFile", "NtWriteFile"]
WRITE_HOOKS = ["WriteFile", "NtWriteFile"]
READ_HOOKS  = ["CreateFileW", "CreateFileA", "NtCreateFile"]


def make_event(hook, path, bytes_val, is_write):
    return {
        "hook":     hook,
        "path":     path,
        "bytes":    bytes_val,
        "is_write": is_write,
    }


def gen_benign():
    """BENIGN: reads of SCADA files, normal system activity."""
    samples = []

    # 1. SCADA file reads (main benign class — monitoring is normal)
    for path in SCADA_FILES:
        for hook in READ_HOOKS:
            samples.append((make_event(hook, path, 0, False), 0))
            # With varying byte counts on subsequent reads
            samples.append((make_event("NtCreateFile", path, random.randint(100, 2000), False), 0))

    # 2. System DLL reads (Python startup)
    for path in SYSTEM_FILES:
        hook = random.choice(READ_HOOKS)
        samples.append((make_event(hook, path, 0, False), 0))

    # 3. Python/app file reads
    for path in PYTHON_FILES + APP_FILES:
        hook = random.choice(READ_HOOKS)
        samples.append((make_event(hook, path, 0, False), 0))

    # 4. Small writes to non-sensitive app paths
    for path in APP_FILES:
        samples.append((make_event("WriteFile", path, random.randint(50, 512), True), 0))

    # 5. Log writes to non-SCADA locations
    log_paths = [
        r"C:\Program Files\MyApp\logs\app.log",
        r"C:\Users\LOQ\AppData\Roaming\MyApp\session.log",
        r"D:\Projects\app\debug.log",
    ]
    for path in log_paths:
        samples.append((make_event("WriteFile", path, random.randint(64, 256), True), 0))

    return samples


def gen_malicious():
    """MALICIOUS: writes to SCADA, suspicious temp writes, bulk enumeration."""
    samples = []

    # 1. Direct writes to SCADA files (highest severity)
    for path in SCADA_FILES:
        for hook in WRITE_HOOKS:
            for size in [128, 512, 4096, 8192]:
                samples.append((make_event(hook, path, size, True), 1))

    # 2. Writes to SCADA with CreateFile write-intent
    for path in SCADA_FILES:
        samples.append((make_event("CreateFileW", path, 0, True), 1))
        samples.append((make_event("CreateFileA", path, 0, True), 1))

    # 3. Suspicious temp writes (exfiltration / staging)
    suspicious_temp = [
        r"C:\Users\LOQ\AppData\Local\Temp\sim_write_log.txt",
        r"C:\Users\LOQ\AppData\Local\Temp\scada_dump.tmp",
        r"C:\Users\LOQ\AppData\Local\Temp\exfil_data.txt",
        r"C:\Temp\payload_out.bin",
        r"C:\Temp\stolen_config.txt",
        r"C:\Users\LOQ\AppData\Local\Temp\grid_backup.zip",
    ]
    for path in suspicious_temp:
        for hook in WRITE_HOOKS:
            samples.append((make_event(hook, path, random.randint(100, 8192), True), 1))
        samples.append((make_event("CreateFileW", path, 0, True), 1))

    # 4. Large bulk writes (ransomware-style pattern)
    for path in SCADA_FILES:
        for size in [65536, 131072, 262144]:
            samples.append((make_event("WriteFile", path, size, True), 1))

    # 5. Writes disguised as reads but wrong hook combination
    for path in SCADA_FILES:
        samples.append((make_event("NtCreateFile", path, 0, True), 1))

    return samples


def augment(samples, n_augmented):
    """
    Light augmentation: vary byte counts and swap similar hooks
    to improve generalisation.
    """
    augmented = []
    hook_swaps = {
        "WriteFile":    "NtWriteFile",
        "NtWriteFile":  "WriteFile",
        "CreateFileW":  "CreateFileA",
        "CreateFileA":  "CreateFileW",
        "NtCreateFile": "CreateFileW",
    }
    for _ in range(n_augmented):
        ev, label = random.choice(samples)
        new_ev = dict(ev)
        # Randomly swap hook variant
        if random.random() < 0.3:
            new_ev["hook"] = hook_swaps.get(ev["hook"], ev["hook"])
        # Randomly vary byte count slightly
        if new_ev["bytes"] > 0:
            new_ev["bytes"] = max(1, int(new_ev["bytes"] * random.uniform(0.5, 2.0)))
        augmented.append((new_ev, label))
    return augmented


def split_and_save(samples):
    random.shuffle(samples)
    n = len(samples)
    train_end = int(n * 0.75)
    val_end   = int(n * 0.875)

    splits = {
        "train": samples[:train_end],
        "val":   samples[train_end:val_end],
        "test":  samples[val_end:],
    }

    for split_name, split_data in splits.items():
        path = os.path.join(OUT_DIR, f"{split_name}.jsonl")
        with open(path, "w") as f:
            for ev, label in split_data:
                f.write(json.dumps({"event": ev, "label": label}) + "\n")
        b = sum(1 for _, l in split_data if l == 1)
        m = sum(1 for _, l in split_data if l == 0)
        print(f"  {split_name:6s}: {len(split_data):5d} samples  "
              f"(BENIGN={m}, MALICIOUS={b})")


def main():
    print("Generating dataset...")

    benign    = gen_benign()
    malicious = gen_malicious()

    print(f"  Base BENIGN   : {len(benign)}")
    print(f"  Base MALICIOUS: {len(malicious)}")

    # Augment to ~5000 balanced total
    target = 2500
    benign    += augment(benign,    target - len(benign))
    malicious += augment(malicious, target - len(malicious))

    all_samples = benign + malicious
    print(f"  Total         : {len(all_samples)}")
    print("\nSplitting and saving...")
    split_and_save(all_samples)
    print(f"\nSaved to: {OUT_DIR}/")


if __name__ == "__main__":
    main()
