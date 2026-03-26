# SCADA Guard - Model Training Pipeline

Complete documentation for training and evaluating the micro-transformer model used in SCADA Guard.

## Overview

SCADA Guard uses a **custom micro-transformer** model for real-time syscall classification:
- **Architecture:** 2 transformer layers, 4 heads, 128-dim embeddings (~120K parameters)
- **Input:** Tokenized file paths + 7 numeric syscall features
- **Output:** Binary classification (BENIGN=0, MALICIOUS=1)
- **Training:** PyTorch with OneCycleLR scheduler
- **Inference:** ONNX Runtime (<2ms on CPU)

## Quick Start

```bash
# Install ML dependencies
pip install -r requirements_ml.txt

# Generate synthetic training data
python data_gen.py

# Build vocabulary from paths
python tokeniser.py

# Train and export to ONNX
python train.py

# Evaluate on test set
python evaluate.py
```

Expected runtime: **2-3 minutes for 30 epochs**

## Detailed Pipeline

### 1. Data Generation (`data_gen.py`)

Generates synthetic SCADA syscall event data in JSONL format.

**Output:**
- `data/train.jsonl` — ~10,000 training samples
- `data/val.jsonl` — ~2,000 validation samples  
- `data/test.jsonl` — ~2,000 test samples

**Label Distribution:**
- **BENIGN (0):** Normal read operations on SCADA/system files
- **MALICIOUS (1):** Writes to SCADA config, suspicious temp access, binary writes

**Sample:**
```json
{"hook": "WriteFile", "path": "C:\\SCADA_ROOT\\grid_config.txt", "bytes": 4096, "is_write": true, "label": 1}
{"hook": "CreateFileW", "path": "C:\\Windows\\System32\\config.txt", "bytes": 0, "is_write": false, "label": 0}
```

**Customization:**
Edit `data_gen.py` to adjust dataset size, class ratios, or add domain-specific patterns.

### 2. Tokenization (`tokeniser.py`)

Converts file paths to sequences of integer token IDs.

**Process:**
1. Parse file paths: split by `\` or `/`
2. Subword tokenization: split by `.` then regex `[a-z0-9]+`
3. Build vocabulary from training set
4. Encode paths: max 32 tokens, pad with 0

**Output:**
- `vocab.json` — Token ID mapping (~2K unique tokens)

**Example:**
```
Path: "C:\SCADA_ROOT\grid_config.txt"
Tokens: ["<START>", "scada", "root", "grid", "config", "txt", "<END>", ...]
IDs: [3, 542, 187, 401, 299, 87, 4, 0, 0, ...]  (padded to 32)
```

**Customization:**
Edit `tokeniser.py` to adjust:
- `MAX_SEQ_LEN = 32` — Max tokens per path
- Special tokens: `<START>, <END>, <UNK>, <PAD>`
- Tokenization regex in `_tokenise()`

### 3. Dataset Loading (`dataset.py`)

PyTorch DataLoader for training/validation/testing.

**Features:**
- Loads JSONL files from `data/` directory
- Splits into train/val/test sets
- Batching and shuffling

**Class Weighting:**
Automatically balances imbalanced datasets with `loss_weight` parameter.

### 4. Model Architecture (`model.py`)

**Micro-Transformer Design:**

```
Input Layer
├─ Path tokens (batch, 32)
│  └─ Embedding (120K params)
│     └─ + Positional Encoding
│
├─ Numeric features (batch, 7)
│  └─ Linear(7→128) + ReLU (1K params)
│     └─ Prepend as token 0 (CLS summary)
│
├─ Concatenate: (batch, 33, 128)
│
├─ TransformerEncoder (2 layers, 4 heads)
│  ├─ Self-attention (4K params/layer)
│  ├─ Feedforward 128→256→128 (66K params/layer)
│  └─ LayerNorm + Residual connections
│
├─ CLS-token pooling: token 0 → (batch, 128)
│
└─ Classification Head
   ├─ Linear(128→64) + ReLU (8K params)
   ├─ Dropout(0.1)
   └─ Linear(64→2) → Logits
      └─ Softmax at inference

Total: ~120K parameters
```

**Why Micro-Transformer:**
- Lightweight: fits in <500KB (PyTorch), <400KB (ONNX)
- Fast: <2ms inference on single core
- Composable: learns both path patterns AND numeric features
- Interpretable: attention weights show which paths matter

**Customization:**
Edit `model.py` constants:

```python
D_MODEL   = 128    # Token embedding dimension (↑ = more capacity)
N_HEADS   = 4      # Attention heads (recommend 4 or 8)
N_LAYERS  = 2      # Transformer layers (↑ = deeper)
D_FF      = 256    # Feedforward hidden size (usually 2-4x D_MODEL)
DROPOUT   = 0.1    # Regularization (0.1-0.2 typical)
N_CLASSES = 2      # Binary classification (don't change)
NUM_FEATS = 7      # Syscall numeric features (don't change)
```

### 5. Training (`train.py`)

Main training script with the following stages:

**Setup:**
1. Load vocabulary and dataset
2. Create model on CPU or GPU
3. Initialize optimizer (AdamW) and scheduler (OneCycleLR)

**Training Loop (30 epochs):**
1. Forward pass through batch
2. Compute loss (CrossEntropyLoss with class weighting)
3. Backward pass
4. Optimizer step (with gradient clipping)
5. Update scheduler

**Validation:**
- After each epoch, evaluate on validation set
- Save model if validation loss improves
- Early stopping after 5 epochs without improvement

**ONNX Export:**
- Export best model to `../scada_guard.onnx`
- Test inference on sample batch to verify

**Output:**
- `checkpoints/best_model.pt` — Best PyTorch model
- `../scada_guard.onnx` — Production ONNX model
- `train_log.json` — Training metrics per epoch

**Customization:**
Edit `train.py` hyperparameters:

```python
EPOCHS       = 30        # Total epochs
BATCH_SIZE   = 64        # Training batch size (↓ if OOM)
LR           = 3e-4      # Learning rate
WEIGHT_DECAY = 1e-3      # L2 regularization
PATIENCE     = 5         # Early stopping patience
```

**Training Log Format:**
```json
{
  "epoch": 1,
  "train_loss": 0.5234,
  "train_acc": 0.8912,
  "val_loss": 0.4891,
  "val_acc": 0.9045,
  "lr": 0.00030,
  "time_sec": 3.2
}
```

### 6. Evaluation (`evaluate.py`)

Comprehensive model evaluation on test set.

**Metrics:**
- **Confusion Matrix:** TP, TN, FP, FN counts
- **Precision:** TP/(TP+FP) — How many predictions were correct
- **Recall:** TP/(TP+FN) — Did we catch all positives
- **F1-Score:** Harmonic mean of Precision & Recall
- **Accuracy:** (TP+TN)/Total
- **Latency:** ONNX inference time per sample

**Output Example:**
```
Test Set Evaluation
═══════════════════════════════════════════
Confusion Matrix:
  True Neg:  1850  False Pos:  150
  False Neg:   25  True Pos:  1975

Per-Class Metrics:
  Class 0 (BENIGN)    – Prec: 0.9254, Rec: 0.9258, F1: 0.9256
  Class 1 (MALICIOUS) – Prec: 0.9295, Rec: 0.9879, F1: 0.9579

Overall:
  Accuracy: 0.9438
  Macro Avg F1: 0.9418

ONNX Inference:
  Fast Mode (32 samples):     1.23 ms per sample
  Slow Mode (1 sample):       2.45 ms per sample
```

## Using Custom Training Data

To train on your own SCADA event data:

### Step 1: Prepare JSONL Files

Create `data/train.jsonl`, `data/val.jsonl`, `data/test.jsonl` with schema:

```json
{
  "hook": "CreateFileW",                    # Syscall type
  "path": "C:\\SCADA_ROOT\\grid_config.txt", # File path
  "bytes": 0,                               # Bytes transferred
  "is_write": false,                        # Write flag
  "label": 0                                # 0=BENIGN, 1=MALICIOUS
}
```

### Step 2: Build Vocabulary

```bash
python tokeniser.py
```

This builds `vocab.json` from your training paths. If paths use domain-specific terminology (e.g., "turbine", "substation"), the vocabulary will include them.

### Step 3: Train

```bash
python train.py
```

The tokenizer will automatically use your vocabulary when encoding paths.

## Performance Tuning

### Model Size ↔ Accuracy Trade-off

| Config | Params | Inference | Val Acc | Use Case |
|--------|--------|-----------|---------|----------|
| Tiny | ~50K | <1ms | 88% | Resource-constrained edge |
| Micro (default) | ~120K | <2ms | 94% | Standard deployment |
| Small | ~300K | ~5ms | 96% | High-accuracy requirements |

**To create a Tiny variant:**
```python
D_MODEL = 64    # (vs 128)
N_HEADS = 2     # (vs 4)
D_FF = 128      # (vs 256)
```

### Training Stability

If loss doesn't converge or diverges:

1. **Reduce learning rate:** `LR = 1e-4` (vs 3e-4)
2. **Increase warm-up:** Modify OneCycleLR in `train.py`
3. **Gradient clipping:** Already enabled (`clip_grad_norm_`)
4. **Class imbalance:** `data_gen.py` generates balanced data by default
5. **Batch size:** Try `BATCH_SIZE = 32` if memory allows

### Inference Optimization

**Quantization (4-bit):**
```python
import onnx
from onnxruntime.quantization import quantize_dynamic

quantize_dynamic("../scada_guard.onnx", "../scada_guard_int8.onnx")
```
Reduces size to ~100KB with negligible accuracy loss.

**Pruning:**
See PyTorch `torch.nn.utils.prune` module to remove low-magnitude weights.

## Troubleshooting

### Issue: `FileNotFoundError: data/ not found`
```bash
python data_gen.py  # Generate datasets first
```

### Issue: `ValueError: vocab.json not found`
```bash
python tokeniser.py  # Build vocab from training data
```

### Issue: Training loss doesn't decrease
- Reduce LR to `1e-4`
- Increase `BATCH_SIZE` for cleaner gradients
- Check data: `print(next(iter(train_loader)))` for NaN/inf values

### Issue: Out of Memory (OOM)
```python
BATCH_SIZE = 32   # Reduce batch size in train.py
```

### Issue: ONNX export fails
Ensure PyTorch and ONNX versions are compatible:
```bash
pip install torch==2.2.0 onnx==1.16.0
```

## Model Deployment

### Production Inference

Once trained, use the model in production with `scada_guard.py`:

```python
from scada_guard import classify, classify_with_confidence

# Basic classification
verdict = classify("CreateFileW", r"C:\SCADA_ROOT\config.txt", 0, False)
# Returns: "BENIGN" or "MALICIOUS"

# With confidence score
verdict, conf = classify_with_confidence("WriteFile", r"C:\temp\log.txt", 2048, True)
# Returns: ("MALICIOUS", 0.9987)
```

### ONNX Model Export Format

The exported ONNX model has:

**Inputs:**
- `token_ids`: shape (batch, 32), dtype int64 — Tokenized paths
- `numeric`: shape (batch, 7), dtype float32 — Numeric syscall features

**Outputs:**
- `prediction`: shape (batch, 2), dtype float32 — Logits [BENIGN, MALICIOUS]

### Integration with Frida

The `defender_core.py` script automatically:
1. Hooks syscalls via Frida
2. Extracts features from each event
3. Calls `classify()` to get verdict
4. Logs to `logs/events.log`

## Advanced Topics

### Transfer Learning

To fine-tune on domain-specific data:

```python
# Load pre-trained model
model = torch.load("checkpoints/best_model.pt")

# Freeze encoder, train only classifier head
for param in model.encoder.parameters():
    param.requires_grad = False

# Train on new data with lower LR
```

### Ensemble Models

Combine multiple models for higher confidence:

```python
models = [
    build_model(vocab_size1),
    build_model(vocab_size2),
    build_model(vocab_size3),
]

# Average predictions
predictions = np.mean([m(x) for m in models], axis=0)
```

### Attention Visualization

Inspect which paths the model focuses on:

```python
# Get attention weights from intermediate layers
attention_weights = model.encoder.layers[0].self_attn.attention_weights
# Shape: (batch, num_heads, seq_len, seq_len)

# Visualize with heatmap
import matplotlib.pyplot as plt
plt.imshow(attention_weights[0, 0].detach().numpy())
plt.colorbar()
plt.show()
```

## References

- [Attention is All You Need](https://arxiv.org/abs/1706.03762) — Transformer paper
- [PyTorch Transformers](https://pytorch.org/docs/stable/nn.html#attention-layers)
- [ONNX Model Zoo](https://github.com/onnx/models)
- [SCADA Security](https://www.cisa.gov/scada-security) — CISA guidelines

## Contributing

Have improvements to the model?

1. **Data improvements:** Better synthetic data in `data_gen.py`
2. **Architecture:** Novel designs in `model.py`
3. **Training:** Better schedulers/optimizers in `train.py`
4. **Evaluation:** Additional metrics in `evaluate.py`

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## Support

- 📧 Email: support@example.com
- 💬 Issues: [GitHub Issues](https://github.com/yourusername/scada-guard/issues)
- 📖 Docs: [Wiki](https://github.com/yourusername/scada-guard/wiki)

---

**Last Updated:** March 22, 2026  
**Model Version:** 1.0.0 (Micro-Transformer, ~120K params, <2ms inference)
