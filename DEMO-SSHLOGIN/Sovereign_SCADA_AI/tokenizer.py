import json

class SCADATokenizer:
    def __init__(self):
        # The 'Alphabet' of your SCADA system
        self.vocab = {"[PAD]": 0, "[UNK]": 1, "[SOS]": 2, "[EOS]": 3}
        self.id_to_token = {}

    def fit(self, texts):
        idx = len(self.vocab)
        for text in texts:
            # Simple space-based splitting for logs
            tokens = text.replace('[', '').replace(']', '').split()
            for token in tokens:
                if token not in self.vocab:
                    self.vocab[token] = idx
                    idx += 1
        self.id_to_token = {v: k for k, v in self.vocab.items()}

    def encode(self, text, max_len=16):
        tokens = text.replace('[', '').replace(']', '').split()
        ids = [self.vocab.get(t, self.vocab["[UNK]"]) for t in tokens]
        # Padding/Truncating to keep the Micro-Transformer input fixed
        ids = ids[:max_len] + [0] * (max_len - len(ids))
        return ids

    def save(self, path="vocab.json"):
        with open(path, 'w') as f:
            json.dump(self.vocab, f)