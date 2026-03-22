"""
train.py — Training Loop + ONNX Export
----------------------------------------
Run:
    python train.py

Outputs:
    ml/checkpoints/best_model.pt
    scada_guard.onnx
"""

import os
import time
import json
import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import OneCycleLR

from tokeniser import load_vocab, VOCAB_PATH, MAX_SEQ_LEN
from dataset   import get_dataloaders, NUM_FEATURES
from model     import build_model, build_padding_mask, SCADAGuardModel

EPOCHS       = 30
BATCH_SIZE   = 64
LR           = 3e-4
WEIGHT_DECAY = 1e-3
PATIENCE     = 5

DATA_DIR  = os.path.join(os.path.dirname(__file__), "data")
CKPT_DIR  = os.path.join(os.path.dirname(__file__), "checkpoints")
ONNX_PATH = os.path.join(os.path.dirname(__file__), "..", "scada_guard.onnx")
LOG_PATH  = os.path.join(os.path.dirname(__file__), "train_log.json")

os.makedirs(CKPT_DIR, exist_ok=True)


def train_epoch(model, loader, criterion, optimiser, scheduler, device):
    model.train()
    total_loss, correct, total = 0.0, 0, 0
    for batch in loader:
        token_ids = batch["token_ids"].to(device)
        numeric   = batch["numeric"].to(device)
        labels    = batch["label"].to(device)
        mask      = build_padding_mask(token_ids)
        logits    = model(token_ids, numeric, mask)
        loss      = criterion(logits, labels)
        optimiser.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimiser.step()
        scheduler.step()
        total_loss += loss.item() * labels.size(0)
        correct    += (logits.argmax(1) == labels).sum().item()
        total      += labels.size(0)
    return total_loss / total, correct / total


@torch.no_grad()
def evaluate(model, loader, criterion, device):
    model.eval()
    total_loss, correct, total = 0.0, 0, 0
    all_preds, all_labels = [], []
    for batch in loader:
        token_ids = batch["token_ids"].to(device)
        numeric   = batch["numeric"].to(device)
        labels    = batch["label"].to(device)
        mask      = build_padding_mask(token_ids)
        logits    = model(token_ids, numeric, mask)
        loss      = criterion(logits, labels)
        preds     = logits.argmax(1)
        total_loss += loss.item() * labels.size(0)
        correct    += (preds == labels).sum().item()
        total      += labels.size(0)
        all_preds.extend(preds.cpu().tolist())
        all_labels.extend(labels.cpu().tolist())
    tp   = sum(p == 1 and l == 1 for p, l in zip(all_preds, all_labels))
    fp   = sum(p == 1 and l == 0 for p, l in zip(all_preds, all_labels))
    fn   = sum(p == 0 and l == 1 for p, l in zip(all_preds, all_labels))
    prec = tp / (tp + fp + 1e-8)
    rec  = tp / (tp + fn + 1e-8)
    f1   = 2 * prec * rec / (prec + rec + 1e-8)
    return total_loss / total, correct / total, f1


def export_onnx(model: SCADAGuardModel, path: str):
    """
    Export using torch.jit.trace + torch.onnx.export (legacy exporter).
    Works without onnxscript on all torch versions.
    """
    model.eval()
    dummy_tokens  = torch.zeros(1, MAX_SEQ_LEN, dtype=torch.long)
    dummy_numeric = torch.zeros(1, NUM_FEATURES, dtype=torch.float32)
    dummy_mask    = torch.zeros(1, MAX_SEQ_LEN,  dtype=torch.bool)

    # Wrap forward to accept only the two main inputs (no optional mask)
    # so ONNX export stays simple and onnxruntime can load it cleanly
    class ExportWrapper(nn.Module):
        def __init__(self, inner):
            super().__init__()
            self.inner = inner
        def forward(self, token_ids, numeric):
            return self.inner(token_ids, numeric, None)

    wrapper = ExportWrapper(model)

    with torch.no_grad():
        torch.onnx.export(
            wrapper,
            (dummy_tokens, dummy_numeric),
            path,
            input_names=["token_ids", "numeric"],
            output_names=["logits"],
            dynamic_axes={
                "token_ids": {0: "batch"},
                "numeric":   {0: "batch"},
                "logits":    {0: "batch"},
            },
            opset_version=14,           # widely supported, no onnxscript needed
            do_constant_folding=True,
            verbose=False,
        )

    size_kb = os.path.getsize(path) / 1024
    print(f"ONNX exported → {path}  ({size_kb:.1f} KB)")


def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    if not os.path.exists(VOCAB_PATH):
        print("ERROR: vocab.json not found. Run:  python tokeniser.py")
        return

    vocab = load_vocab(VOCAB_PATH)
    print(f"Vocab size: {len(vocab)}")

    print("\nLoading data...")
    train_loader, val_loader, test_loader = get_dataloaders(
        DATA_DIR, vocab, batch_size=BATCH_SIZE
    )

    print("\nBuilding model...")
    model = build_model(len(vocab)).to(device)

    criterion = nn.CrossEntropyLoss()
    optimiser = AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    scheduler = OneCycleLR(
        optimiser,
        max_lr=LR,
        steps_per_epoch=len(train_loader),
        epochs=EPOCHS,
        pct_start=0.1,
    )

    print(f"\nTraining for up to {EPOCHS} epochs (patience={PATIENCE})...")
    print(f"{'Epoch':>6}  {'Train loss':>10}  {'Train acc':>9}  "
          f"{'Val loss':>9}  {'Val acc':>8}  {'F1':>6}  {'Time':>6}")
    print("-" * 65)

    best_val_loss  = float("inf")
    best_f1        = 0.0
    patience_count = 0
    history        = []

    for epoch in range(1, EPOCHS + 1):
        t0 = time.time()
        tr_loss, tr_acc         = train_epoch(model, train_loader, criterion, optimiser, scheduler, device)
        vl_loss, vl_acc, f1     = evaluate(model, val_loader, criterion, device)
        elapsed = time.time() - t0

        print(f"{epoch:>6}  {tr_loss:>10.4f}  {tr_acc:>9.4f}  "
              f"{vl_loss:>9.4f}  {vl_acc:>8.4f}  {f1:>6.4f}  {elapsed:>5.1f}s")

        history.append({"epoch": epoch, "train_loss": tr_loss, "train_acc": tr_acc,
                         "val_loss": vl_loss, "val_acc": vl_acc, "f1": f1})

        if vl_loss < best_val_loss:
            best_val_loss  = vl_loss
            best_f1        = f1
            patience_count = 0
            ckpt = os.path.join(CKPT_DIR, "best_model.pt")
            torch.save({"epoch": epoch, "state_dict": model.state_dict(),
                        "val_loss": vl_loss, "val_acc": vl_acc, "f1": f1,
                        "vocab_size": len(vocab)}, ckpt)
        else:
            patience_count += 1
            if patience_count >= PATIENCE:
                print(f"\nEarly stopping at epoch {epoch}")
                break

    print("\nLoading best checkpoint for test evaluation...")
    ckpt = torch.load(os.path.join(CKPT_DIR, "best_model.pt"), map_location=device,
                      weights_only=True)
    model.load_state_dict(ckpt["state_dict"])
    ts_loss, ts_acc, ts_f1 = evaluate(model, test_loader, criterion, device)
    print(f"Test   loss={ts_loss:.4f}  acc={ts_acc:.4f}  F1={ts_f1:.4f}")

    with open(LOG_PATH, "w") as f:
        json.dump({"history": history, "best_val_loss": best_val_loss,
                   "best_f1": best_f1, "test_loss": ts_loss,
                   "test_acc": ts_acc, "test_f1": ts_f1}, f, indent=2)
    print(f"Training log saved → {LOG_PATH}")

    print("\nExporting to ONNX...")
    export_onnx(model, ONNX_PATH)

    print("\n── Done ─────────────────────────────────────────────")
    print(f"  Best val F1 : {best_f1:.4f}")
    print(f"  Test F1     : {ts_f1:.4f}")
    print(f"  ONNX model  : {ONNX_PATH}")
    print(f"\nNext step:")
    print(f"  python ml\\evaluate.py")
    print(f"  Then in defender_core.py change:")
    print(f"    from llm_guard  import classify")
    print(f"    to:")
    print(f"    from scada_guard import classify")


if __name__ == "__main__":
    main()
