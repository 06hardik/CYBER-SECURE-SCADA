import torch
import torch.nn as nn
import torch.optim as optim
import pandas as pd
from torch.utils.data import DataLoader, TensorDataset
from tokenizer import SCADATokenizer
from model import MicroTransformer

def train_model(epochs=5, batch_size=32, learning_rate=0.001):
    # 1. Load the data
    print("Loading data...")
    df = pd.read_csv('scada_logs.csv')
    
    # 2. Tokenize the logs
    tokenizer = SCADATokenizer()
    tokenizer.fit(df['log'].tolist())
    tokenizer.save("vocab.json") # Save for later inference
    
    encoded_logs = [tokenizer.encode(log) for log in df['log'].tolist()]
    X = torch.tensor(encoded_logs)
    y = torch.tensor(df['label'].tolist(), dtype=torch.float32).reshape(-1, 1)

    # 3. Create a DataLoader for batching
    dataset = TensorDataset(X, y)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    # 4. Initialize Model, Loss, and Optimizer
    model = MicroTransformer(vocab_size=len(tokenizer.vocab))
    criterion = nn.BCELoss() # Binary Cross Entropy
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)

    # 5. The Training Loop
    print(f"Starting training for {epochs} epochs...")
    model.train()
    for epoch in range(epochs):
        total_loss = 0
        for batch_X, batch_y in loader:
            optimizer.zero_grad()           # Clear old gradients
            outputs = model(batch_X)        # Forward pass
            loss = criterion(outputs, batch_y) # Calculate error
            loss.backward()                 # Backpropagation
            optimizer.step()                # Update weights
            total_loss += loss.item()
        
        avg_loss = total_loss / len(loader)
        print(f"Epoch [{epoch+1}/{epochs}], Loss: {avg_loss:.4f}")

    # 6. Save the trained weights
    torch.save(model.state_dict(), "scada_model.pth")
    print("Training complete. Model weights saved to 'scada_model.pth'")

if __name__ == "__main__":
    train_model()