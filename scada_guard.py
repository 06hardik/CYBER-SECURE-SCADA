"""
scada_guard.py — ONNX Inference Drop-in for llm_guard.py
----------------------------------------------------------
Identical public interface to llm_guard.py:

    from scada_guard import classify
    verdict = classify(hook, path, bytes_count, is_write)
    # returns "MALICIOUS" or "BENIGN"

Loads scada_guard.onnx once at module import.
Inference: <2ms on CPU. No network, no Ollama, fully offline.

Usage in defender_core.py — just change one import line:
    # from llm_guard  import classify
    from scada_guard import classify
"""

import os
import math
import json
import numpy as np

# ── Paths ─────────────────────────────────────────────────────────────────────
_HERE      = os.path.dirname(os.path.abspath(__file__))
ONNX_PATH  = os.path.join(_HERE, "scada_guard.onnx")
VOCAB_PATH = os.path.join(_HERE, "ml", "vocab.json")
MAX_SEQ_LEN = 32

# ── Load vocab ────────────────────────────────────────────────────────────────
def _load_vocab():
    if not os.path.exists(VOCAB_PATH):
        raise FileNotFoundError(
            f"vocab.json not found at {VOCAB_PATH}\n"
            "  Run:  cd ml && python data_gen.py && python tokeniser.py && python train.py"
        )
    with open(VOCAB_PATH) as f:
        return json.load(f)

_VOCAB: dict | None = None

def _get_vocab() -> dict:
    global _VOCAB
    if _VOCAB is None:
        _VOCAB = _load_vocab()
    return _VOCAB

# ── Load ONNX session ─────────────────────────────────────────────────────────
_SESSION = None

def _get_session():
    global _SESSION
    if _SESSION is None:
        try:
            import onnxruntime as ort
        except ImportError:
            raise ImportError(
                "onnxruntime not installed.\n"
                "  Run:  pip install onnxruntime"
            )
        if not os.path.exists(ONNX_PATH):
            raise FileNotFoundError(
                f"ONNX model not found: {ONNX_PATH}\n"
                "  Run:  cd ml && python train.py"
            )
        _SESSION = ort.InferenceSession(
            ONNX_PATH,
            providers=["CPUExecutionProvider"]
        )
    return _SESSION

# ── Tokeniser (inline — no import dependency) ─────────────────────────────────
import re

def _tokenise(path: str) -> list[str]:
    path = path.lower()
    path = re.sub(r"^\\\\\?\\\\?", "", path)
    parts = re.split(r"[/\\]", path)
    tokens = []
    for part in parts:
        if not part:
            continue
        for sp in part.split("."):
            tokens.extend(re.findall(r"[a-z0-9]+", sp))
    return tokens or ["<UNK>"]

def _encode(path: str, vocab: dict) -> list[int]:
    PAD, UNK, START, END = 0, vocab.get("<UNK>", 1), vocab.get("<START>", 3), vocab.get("<END>", 4)
    tokens = ["<START>"] + _tokenise(path) + ["<END>"]
    ids    = [vocab.get(t, UNK) for t in tokens]
    ids    = ids[:MAX_SEQ_LEN]
    ids   += [PAD] * (MAX_SEQ_LEN - len(ids))
    return ids

# ── Numeric feature extraction ────────────────────────────────────────────────
def _numeric(hook: str, path: str, bytes_count: int, is_write: bool) -> list[float]:
    HOOK_IDS = {
        "CreateFileW": 0, "CreateFileA": 1, "NtCreateFile": 2,
        "WriteFile": 3,   "NtWriteFile": 4,
    }
    up = path.upper()
    return [
        math.log1p(bytes_count),
        float(is_write),
        float(HOOK_IDS.get(hook, 2)),
        float("SCADA"      in up),
        float("\\TEMP\\"   in up or "/TMP/" in up),
        float("\\WINDOWS\\" in up or "SYSTEM32" in up),
        float(up.endswith(".PYD") or up.endswith(".DLL")),
    ]

# ── Softmax ───────────────────────────────────────────────────────────────────
def _softmax(x):
    e = np.exp(x - x.max())
    return e / e.sum()

# ── Public API ────────────────────────────────────────────────────────────────

def classify(hook: str, path: str, bytes_count: int, is_write: bool) -> str:
    """
    Classify a syscall event.

    Returns
    -------
    'MALICIOUS' or 'BENIGN'
    Defaults to 'MALICIOUS' on any error (fail-safe).
    """
    try:
        vocab   = _get_vocab()
        session = _get_session()

        token_ids = np.array([_encode(path, vocab)],           dtype=np.int64)
        numeric   = np.array([_numeric(hook, path, bytes_count, is_write)],
                              dtype=np.float32)

        logits = session.run(None, {
            "token_ids": token_ids,
            "numeric":   numeric,
        })[0][0]   # shape [2]

        probs    = _softmax(logits)
        pred_idx = int(probs.argmax())
        return ["BENIGN", "MALICIOUS"][pred_idx]

    except Exception as e:
        print(f"[scada_guard] Error: {e} → defaulting to MALICIOUS")
        return "MALICIOUS"


def classify_with_confidence(
    hook: str, path: str, bytes_count: int, is_write: bool
) -> tuple[str, float]:
    """
    Same as classify() but also returns the confidence score.

    Returns
    -------
    (verdict, confidence)  e.g. ('MALICIOUS', 0.9987)
    """
    try:
        vocab   = _get_vocab()
        session = _get_session()

        token_ids = np.array([_encode(path, vocab)],           dtype=np.int64)
        numeric   = np.array([_numeric(hook, path, bytes_count, is_write)],
                              dtype=np.float32)

        logits = session.run(None, {
            "token_ids": token_ids,
            "numeric":   numeric,
        })[0][0]

        probs    = _softmax(logits)
        pred_idx = int(probs.argmax())
        verdict  = ["BENIGN", "MALICIOUS"][pred_idx]
        conf     = float(probs[pred_idx])
        return verdict, conf

    except Exception as e:
        print(f"[scada_guard] Error: {e} → defaulting to MALICIOUS")
        return "MALICIOUS", 1.0


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("── scada_guard.py  Standalone Test ──────────────────────────")

    cases = [
        ("CreateFileW", r"C:\SCADA_ROOT\grid_config.txt",         0,    False, "BENIGN"),
        ("CreateFileW", r"C:\SCADA_ROOT\turbine_auth.csv",        0,    False, "BENIGN"),
        ("WriteFile",   r"C:\SCADA_ROOT\safety_limits.txt",    4096,  True,  "MALICIOUS"),
        ("WriteFile",   r"C:\Temp\sim_write_log.txt",           166,  True,  "MALICIOUS"),
        ("CreateFileW", r"C:\Windows\System32\ntdll.dll",         0,  False, "BENIGN"),
        ("WriteFile",   r"C:\Program Files\MyApp\app.log",      128,  True,  "BENIGN"),
    ]

    print(f"\n{'Description':30s}  {'Expected':10}  {'Got':10}  {'Conf':>6}  {'OK':>4}")
    for hook, path, byt, wr, expected in cases:
        verdict, conf = classify_with_confidence(hook, path, byt, wr)
        ok = "PASS" if verdict == expected else "FAIL"
        desc = f"{'WRITE' if wr else 'READ':5s}  {os.path.basename(path)}"
        print(f"  {desc:28s}  {expected:10}  {verdict:10}  {conf:6.3f}  {ok}")
    print()
