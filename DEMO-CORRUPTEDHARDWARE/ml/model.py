"""
model.py — SCADA Micro-Transformer
------------------------------------
Architecture:
  path tokens  →  Embedding(vocab_size, d=128)  +  PositionalEncoding
                          ↓
  numeric(7)   →  Linear(7 → 128) → ReLU  (prepended as token 0)
                          ↓
         TransformerEncoder(2 layers, 4 heads, ff=256, dropout=0.1)
                          ↓
               CLS-token pool  →  [batch, 128]
                          ↓
         Linear(128→64) → ReLU → Dropout → Linear(64→2)
                          ↓
               logits  →  softmax at inference

Fix: use a single d_model=128 throughout. Numeric features are
projected to d_model and prepended as a learned summary token —
no concat along d_model needed.

Total params: ~120 K  —  runs in <2ms CPU inference
"""

import torch
import torch.nn as nn
import math

D_MODEL   = 128
N_HEADS   = 4
N_LAYERS  = 2
D_FF      = 256
DROPOUT   = 0.1
N_CLASSES = 2
NUM_FEATS = 7


class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = 64, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(dropout)
        pe  = torch.zeros(max_len, d_model)
        pos = torch.arange(0, max_len).unsqueeze(1).float()
        div = torch.exp(
            torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(pos * div)
        pe[:, 1::2] = torch.cos(pos * div)
        self.register_buffer("pe", pe.unsqueeze(0))  # [1, max_len, d_model]

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.pe[:, :x.size(1)]
        return self.dropout(x)


class SCADAGuardModel(nn.Module):
    def __init__(self, vocab_size: int):
        super().__init__()

        # Token embedding: each token → d_model
        self.token_embed = nn.Embedding(vocab_size, D_MODEL, padding_idx=0)
        self.pos_enc     = PositionalEncoding(D_MODEL, dropout=DROPOUT)

        # Numeric summary token: project 7 features → d_model
        # This becomes position-0 in the sequence (like a CLS token)
        self.num_proj = nn.Sequential(
            nn.Linear(NUM_FEATS, D_MODEL),
            nn.ReLU(),
            nn.Dropout(DROPOUT),
        )

        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=D_MODEL,
            nhead=N_HEADS,
            dim_feedforward=D_FF,
            dropout=DROPOUT,
            batch_first=True,
            norm_first=True,
        )
        self.transformer = nn.TransformerEncoder(
            encoder_layer,
            num_layers=N_LAYERS,
            enable_nested_tensor=False,
        )

        # Classifier head reads from the numeric summary token (position 0)
        self.classifier = nn.Sequential(
            nn.Linear(D_MODEL, 64),
            nn.ReLU(),
            nn.Dropout(DROPOUT),
            nn.Linear(64, N_CLASSES),
        )

    def forward(
        self,
        token_ids:    torch.Tensor,            # [batch, seq_len]
        numeric:      torch.Tensor,            # [batch, NUM_FEATS]
        padding_mask: torch.Tensor | None = None,  # [batch, seq_len]
    ) -> torch.Tensor:
        """Returns logits [batch, 2]."""

        # 1. Numeric summary token: [batch, 1, D_MODEL]
        num_tok = self.num_proj(numeric).unsqueeze(1)

        # 2. Token embeddings + positional encoding: [batch, seq_len, D_MODEL]
        tok = self.pos_enc(self.token_embed(token_ids))

        # 3. Prepend numeric token → [batch, seq_len+1, D_MODEL]
        x = torch.cat([num_tok, tok], dim=1)

        # 4. Extend padding mask to cover the numeric token (never masked)
        if padding_mask is not None:
            # [batch, 1] of False prepended
            prefix = torch.zeros(
                padding_mask.size(0), 1,
                dtype=torch.bool, device=padding_mask.device
            )
            mask = torch.cat([prefix, padding_mask], dim=1)  # [batch, seq_len+1]
        else:
            mask = None

        # 5. Transformer
        x = self.transformer(x, src_key_padding_mask=mask)

        # 6. Use position-0 (numeric summary token) as the pooled representation
        pooled = x[:, 0, :]  # [batch, D_MODEL]

        return self.classifier(pooled)

    def predict_proba(self, token_ids, numeric):
        with torch.no_grad():
            return torch.softmax(self.forward(token_ids, numeric), dim=-1)

    def predict(self, token_ids, numeric):
        probs     = self.predict_proba(token_ids, numeric)
        preds     = probs.argmax(dim=-1).tolist()
        confs     = probs.max(dim=-1).values.tolist()
        label_map = {0: "BENIGN", 1: "MALICIOUS"}
        return [label_map[p] for p in preds], confs


def build_model(vocab_size: int) -> SCADAGuardModel:
    model    = SCADAGuardModel(vocab_size)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"Model built: {n_params:,} parameters")
    return model


def build_padding_mask(token_ids: torch.Tensor, pad_idx: int = 0) -> torch.Tensor:
    """True where token == PAD (should be ignored by transformer)."""
    return token_ids == pad_idx


if __name__ == "__main__":
    VOCAB_SIZE = 100
    BATCH, SEQ = 4, 32

    model     = build_model(VOCAB_SIZE)
    model.eval()
    token_ids = torch.randint(0, VOCAB_SIZE, (BATCH, SEQ))
    numeric   = torch.randn(BATCH, NUM_FEATS)
    mask      = build_padding_mask(token_ids)

    logits        = model(token_ids, numeric, mask)
    labels, confs = model.predict(token_ids, numeric)
    print(f"Logits shape : {tuple(logits.shape)}")
    print(f"Labels       : {labels}")
    print(f"Confidences  : {[f'{c:.3f}' for c in confs]}")
