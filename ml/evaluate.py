"""
evaluate.py — Model Evaluation + Latency Benchmark
----------------------------------------------------
Loads the best checkpoint, runs on the test set,
prints a confusion matrix and per-class metrics,
and benchmarks ONNX inference latency.

Run:
    python evaluate.py
"""

import os
import time
import json
import torch
import numpy as np

from tokeniser import load_vocab, VOCAB_PATH, MAX_SEQ_LEN, encode
from dataset   import get_dataloaders, extract_numeric
from model     import build_model, build_padding_mask

DATA_DIR  = os.path.join(os.path.dirname(__file__), "data")
CKPT_DIR  = os.path.join(os.path.dirname(__file__), "checkpoints")
ONNX_PATH = os.path.join(os.path.dirname(__file__), "..", "scada_guard.onnx")

LABEL_NAMES = ["BENIGN", "MALICIOUS"]


# ── PyTorch evaluation ────────────────────────────────────────────────────────

def full_eval(model, loader, device):
    model.eval()
    all_preds, all_labels, all_probs = [], [], []

    with torch.no_grad():
        for batch in loader:
            token_ids = batch["token_ids"].to(device)
            numeric   = batch["numeric"].to(device)
            labels    = batch["label"].to(device)

            mask   = build_padding_mask(token_ids)
            logits = model(token_ids, numeric, mask)
            probs  = torch.softmax(logits, dim=-1)
            preds  = logits.argmax(1)

            all_preds.extend(preds.cpu().tolist())
            all_labels.extend(labels.cpu().tolist())
            all_probs.extend(probs.cpu().tolist())

    return all_preds, all_labels, all_probs


def confusion_matrix(preds, labels, n_classes=2):
    cm = [[0] * n_classes for _ in range(n_classes)]
    for p, l in zip(preds, labels):
        cm[l][p] += 1
    return cm


def print_report(preds, labels):
    cm  = confusion_matrix(preds, labels)
    acc = sum(p == l for p, l in zip(preds, labels)) / len(preds)

    print("\n── Confusion Matrix ─────────────────────────────────")
    print(f"{'':15s}  {'Pred BENIGN':>12}  {'Pred MALICIOUS':>15}")
    for i, name in enumerate(LABEL_NAMES):
        print(f"  True {name:9s}  {cm[i][0]:>12}  {cm[i][1]:>15}")

    print(f"\n── Per-class metrics ────────────────────────────────")
    print(f"{'Class':>12}  {'Precision':>10}  {'Recall':>8}  {'F1':>8}")
    for i, name in enumerate(LABEL_NAMES):
        tp = cm[i][i]
        fp = sum(cm[j][i] for j in range(2)) - tp
        fn = sum(cm[i])   - tp
        prec = tp / (tp + fp + 1e-8)
        rec  = tp / (tp + fn + 1e-8)
        f1   = 2 * prec * rec / (prec + rec + 1e-8)
        print(f"  {name:>12}  {prec:>10.4f}  {rec:>8.4f}  {f1:>8.4f}")

    print(f"\n  Overall accuracy : {acc:.4f}")


# ── ONNX latency benchmark ────────────────────────────────────────────────────

def benchmark_onnx(vocab, n_runs=1000):
    try:
        import onnxruntime as ort
    except ImportError:
        print("\n[evaluate] onnxruntime not installed — skipping ONNX benchmark.")
        print("  pip install onnxruntime")
        return

    if not os.path.exists(ONNX_PATH):
        print(f"\n[evaluate] ONNX model not found: {ONNX_PATH}")
        return

    sess = ort.InferenceSession(
        ONNX_PATH,
        providers=["CPUExecutionProvider"]
    )

    # Warm up
    test_path = r"C:\SCADA_ROOT\pressure_thresholds.txt"
    test_event = {
        "hook": "WriteFile", "path": test_path,
        "bytes": 4096, "is_write": True,
    }
    token_ids = np.array([encode(test_path, vocab, MAX_SEQ_LEN)], dtype=np.int64)
    numeric   = np.array([extract_numeric(test_event)],          dtype=np.float32)

    for _ in range(10):
        sess.run(None, {"token_ids": token_ids, "numeric": numeric})

    # Timed runs
    times = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        sess.run(None, {"token_ids": token_ids, "numeric": numeric})
        times.append((time.perf_counter() - t0) * 1000)

    times = sorted(times)
    print(f"\n── ONNX Inference Latency ({n_runs} runs) ───────────────")
    print(f"  Mean  : {sum(times)/len(times):.3f} ms")
    print(f"  Median: {times[len(times)//2]:.3f} ms")
    print(f"  p95   : {times[int(len(times)*0.95)]:.3f} ms")
    print(f"  p99   : {times[int(len(times)*0.99)]:.3f} ms")
    print(f"  Max   : {times[-1]:.3f} ms")


# ── Qualitative spot-check ────────────────────────────────────────────────────

def spot_check(vocab):
    try:
        import onnxruntime as ort
    except ImportError:
        return

    if not os.path.exists(ONNX_PATH):
        return

    sess = ort.InferenceSession(ONNX_PATH, providers=["CPUExecutionProvider"])

    cases = [
        # (description, event, expected)
        ("SCADA read  (BENIGN)",
         {"hook": "CreateFileW", "path": r"C:\SCADA_ROOT\grid_config.txt",
          "bytes": 0, "is_write": False}, "BENIGN"),
        ("SCADA write (MALICIOUS)",
         {"hook": "WriteFile",   "path": r"C:\SCADA_ROOT\safety_limits.txt",
          "bytes": 4096, "is_write": True},  "MALICIOUS"),
        ("Temp write  (MALICIOUS)",
         {"hook": "WriteFile",   "path": r"C:\Temp\sim_write_log.txt",
          "bytes": 166, "is_write": True},   "MALICIOUS"),
        ("System read (BENIGN)",
         {"hook": "CreateFileW", "path": r"C:\Windows\System32\ntdll.dll",
          "bytes": 0, "is_write": False}, "BENIGN"),
        ("App write   (BENIGN)",
         {"hook": "WriteFile",   "path": r"C:\Program Files\MyApp\app.log",
          "bytes": 128, "is_write": True},   "BENIGN"),
    ]

    print("\n── Spot Check ───────────────────────────────────────")
    print(f"{'Case':28s}  {'Expected':10}  {'Got':10}  {'Conf':>6}  {'OK':>4}")
    for desc, ev, expected in cases:
        token_ids = np.array([encode(ev["path"], vocab, MAX_SEQ_LEN)], dtype=np.int64)
        numeric   = np.array([extract_numeric(ev)],                    dtype=np.float32)
        logits    = sess.run(None, {"token_ids": token_ids, "numeric": numeric})[0]
        probs     = np.exp(logits) / np.exp(logits).sum(axis=1, keepdims=True)
        pred_idx  = int(probs.argmax())
        pred      = ["BENIGN", "MALICIOUS"][pred_idx]
        conf      = float(probs[0, pred_idx])
        ok        = "✓" if pred == expected else "✗"
        print(f"  {desc:26s}  {expected:10}  {pred:10}  {conf:6.3f}  {ok}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    device = torch.device("cpu")

    vocab = load_vocab(VOCAB_PATH)
    print(f"Vocab size: {len(vocab)}")

    ckpt_path = os.path.join(CKPT_DIR, "best_model.pt")
    if not os.path.exists(ckpt_path):
        print(f"ERROR: {ckpt_path} not found. Run train.py first.")
        return

    ckpt  = torch.load(ckpt_path, map_location=device)
    model = build_model(len(vocab)).to(device)
    model.load_state_dict(ckpt["state_dict"])
    print(f"Loaded checkpoint (epoch {ckpt['epoch']}, val_loss={ckpt['val_loss']:.4f})")

    _, _, test_loader = get_dataloaders(DATA_DIR, vocab, batch_size=128)
    preds, labels, _  = full_eval(model, test_loader, device)

    print_report(preds, labels)
    benchmark_onnx(vocab)
    spot_check(vocab)


if __name__ == "__main__":
    main()
