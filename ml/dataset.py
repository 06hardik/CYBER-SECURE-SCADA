"""
dataset.py — PyTorch Dataset for SCADA Syscall Events
------------------------------------------------------
Loads .jsonl files produced by data_gen.py and returns
(token_ids, numeric_features, label) tensors.

Numeric feature vector (7 dims):
  [0] log1p(bytes)          — write size, log-scaled
  [1] is_write              — 1 if write operation
  [2] hook_id               — 0-4 encoding of API hook
  [3] is_scada              — path contains SCADA
  [4] is_temp               — path is in Temp dir
  [5] is_system             — path is in Windows/System32
  [6] is_pyd_or_dll         — path ends in .pyd or .dll
"""

import json
import math
import os
import torch
from torch.utils.data import Dataset, DataLoader

from tokeniser import encode, load_vocab, MAX_SEQ_LEN

HOOK_IDS = {
    "CreateFileW":  0,
    "CreateFileA":  1,
    "NtCreateFile": 2,
    "WriteFile":    3,
    "NtWriteFile":  4,
}
NUM_FEATURES = 7


def extract_numeric(event: dict) -> list[float]:
    path     = event["path"].upper()
    hook     = event["hook"]
    bytes_v  = event.get("bytes", 0)
    is_write = float(event.get("is_write", False))

    return [
        math.log1p(bytes_v),                                    # [0]
        is_write,                                               # [1]
        float(HOOK_IDS.get(hook, 2)),                          # [2]
        float("SCADA"    in path),                             # [3]
        float("\\TEMP\\" in path or "/TMP/" in path),          # [4]
        float("\\WINDOWS\\" in path or "SYSTEM32" in path),   # [5]
        float(path.endswith(".PYD") or path.endswith(".DLL")), # [6]
    ]


class SyscallDataset(Dataset):
    def __init__(self, jsonl_path: str, vocab: dict):
        self.vocab   = vocab
        self.samples = []

        with open(jsonl_path) as f:
            for line in f:
                record = json.loads(line.strip())
                ev     = record["event"]
                label  = record["label"]

                token_ids = encode(ev["path"], vocab, MAX_SEQ_LEN)
                numeric   = extract_numeric(ev)

                self.samples.append({
                    "token_ids": torch.tensor(token_ids, dtype=torch.long),
                    "numeric":   torch.tensor(numeric,   dtype=torch.float32),
                    "label":     torch.tensor(label,     dtype=torch.long),
                })

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        return self.samples[idx]


def get_dataloaders(data_dir: str, vocab: dict,
                    batch_size: int = 64) -> tuple:
    """
    Returns (train_loader, val_loader, test_loader).
    """
    loaders = {}
    for split in ("train", "val", "test"):
        path    = os.path.join(data_dir, f"{split}.jsonl")
        dataset = SyscallDataset(path, vocab)
        shuffle = (split == "train")
        loaders[split] = DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=shuffle,
            num_workers=0,
        )
        print(f"  {split:6s}: {len(dataset):5d} samples  "
              f"batch_size={batch_size}")

    return loaders["train"], loaders["val"], loaders["test"]


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    from tokeniser import load_vocab, VOCAB_PATH

    vocab = load_vocab(VOCAB_PATH)
    ds    = SyscallDataset(
        os.path.join(os.path.dirname(__file__), "data", "train.jsonl"),
        vocab
    )

    sample = ds[0]
    print("Sample:")
    print(f"  token_ids : {sample['token_ids'][:8]}...")
    print(f"  numeric   : {sample['numeric']}")
    print(f"  label     : {sample['label'].item()}")
    print(f"  total     : {len(ds)} samples")
