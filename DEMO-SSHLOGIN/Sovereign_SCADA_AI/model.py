import torch
import torch.nn as nn

class MicroTransformer(nn.Module):
    def __init__(self, vocab_size, embed_dim=64, heads=4, num_layers=2):
        super(MicroTransformer, self).__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim)
        
        # This is the core 'Attention' mechanism
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_dim, 
            nhead=heads, 
            dim_feedforward=128, 
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        # Final classification layer: Normal vs Anomaly
        self.fc = nn.Linear(embed_dim, 1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        # x shape: (batch_size, seq_len)
        x = self.embedding(x) # (batch_size, seq_len, embed_dim)
        x = self.transformer(x)
        # We take the mean of the sequence embeddings to get a 'sentence' representation
        x = torch.mean(x, dim=1) 
        x = self.fc(x)
        return self.sigmoid(x)