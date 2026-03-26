"""
tokeniser.py — Path Tokeniser
------------------------------
Splits file paths into sub-tokens, builds a vocabulary,
and provides encode/decode utilities.

Run standalone to build vocab from training data:
    python tokeniser.py

Saves: ml/vocab.json
"""

import re
import json
import os
from collections import Counter

VOCAB_PATH = os.path.join(os.path.dirname(__file__), "vocab.json")
DATA_DIR   = os.path.join(os.path.dirname(__file__), "data")

# Special tokens
PAD   = "<PAD>"    # index 0
UNK   = "<UNK>"    # index 1
SEP   = "<SEP>"    # index 2  — separates path segments
START = "<START>"  # index 3
END   = "<END>"    # index 4

SPECIAL_TOKENS = [PAD, UNK, SEP, START, END]
MAX_SEQ_LEN    = 32   # max tokens per path (truncate/pad to this)
MIN_FREQ       = 2    # minimum frequency to keep a token in vocab


def tokenise_path(path: str) -> list[str]:
    """
    Split a file path into meaningful sub-tokens.

    Examples:
      C:\\SCADA_ROOT\\pressure_thresholds.txt
        → ['c:', 'scada_root', 'pressure', 'thresholds', 'txt']

      \\?\\C:\\Users\\LOQ\\AppData\\Local\\Temp\\sim_write_log.txt
        → ['users', 'loq', 'appdata', 'local', 'temp', 'sim', 'write', 'log', 'txt']
    """
    # Normalise separators and strip NT prefix
    path = path.lower()
    path = path.replace("\\\\?\\\\", "").replace("\\\\?\\", "").replace("\\\\", "\\")

    # Split on path separators
    parts = re.split(r"[/\\]", path)

    tokens = []
    for part in parts:
        if not part:
            continue
        # Split on dots (extension separation)
        sub_parts = part.split(".")
        for sp in sub_parts:
            if not sp:
                continue
            # Split CamelCase and snake_case
            words = re.findall(r"[a-z0-9]+", sp)
            tokens.extend(words)

    return tokens if tokens else [UNK]


def build_vocab(paths: list[str], min_freq: int = MIN_FREQ) -> dict:
    """Build vocab from a list of file paths."""
    counter = Counter()
    for path in paths:
        tokens = tokenise_path(path)
        counter.update(tokens)

    # Start with special tokens
    vocab = {tok: i for i, tok in enumerate(SPECIAL_TOKENS)}

    # Add frequent tokens
    for token, freq in counter.most_common():
        if freq >= min_freq and token not in vocab:
            vocab[token] = len(vocab)

    return vocab


def encode(path: str, vocab: dict,
           max_len: int = MAX_SEQ_LEN) -> list[int]:
    """
    Encode a path string to a padded integer sequence.
    Returns a list of length max_len.
    """
    tokens  = [START] + tokenise_path(path) + [END]
    ids     = [vocab.get(t, vocab[UNK]) for t in tokens]

    # Truncate
    ids = ids[:max_len]
    # Pad
    ids += [vocab[PAD]] * (max_len - len(ids))
    return ids


def save_vocab(vocab: dict, path: str = VOCAB_PATH):
    with open(path, "w") as f:
        json.dump(vocab, f, indent=2)
    print(f"Vocab saved: {path}  ({len(vocab)} tokens)")


def load_vocab(path: str = VOCAB_PATH) -> dict:
    with open(path) as f:
        return json.load(f)


def vocab_size(vocab: dict) -> int:
    return len(vocab)


# ── Standalone: build vocab from training data ────────────────────────────────

def main():
    import json as _json

    train_path = os.path.join(DATA_DIR, "train.jsonl")
    if not os.path.exists(train_path):
        print(f"[tokeniser] ERROR: {train_path} not found.")
        print("  Run:  python data_gen.py  first.")
        return

    paths = []
    with open(train_path) as f:
        for line in f:
            record = _json.loads(line)
            paths.append(record["event"]["path"])

    print(f"Building vocab from {len(paths)} paths...")
    vocab = build_vocab(paths)
    save_vocab(vocab)

    # Quick test
    test_path = r"C:\SCADA_ROOT\pressure_thresholds.txt"
    tokens = tokenise_path(test_path)
    ids    = encode(test_path, vocab)
    print(f"\nTest tokenisation:")
    print(f"  Path  : {test_path}")
    print(f"  Tokens: {tokens}")
    print(f"  IDs   : {ids[:10]}...")


if __name__ == "__main__":
    main()
