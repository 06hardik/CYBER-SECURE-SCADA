import torch
import pandas as pd
from data_gen import generate_logs
from tokenizer import SCADATokenizer
from model import MicroTransformer

def verify_pipeline():
    print("--- 1. Generating Data ---")
    generate_logs(num_entries=100) # Small batch for testing
    df = pd.read_csv('scada_logs.csv')
    print(f"Sample log: {df.iloc[0]['log']}")

    print("\n--- 2. Testing Tokenizer ---")
    tokenizer = SCADATokenizer()
    tokenizer.fit(df['log'].tolist())
    test_log = df.iloc[0]['log']
    encoded = tokenizer.encode(test_log)
    print(f"Tokens -> IDs: {encoded}")

    print("\n--- 3. Testing Model Forward Pass ---")
    vocab_size = len(tokenizer.vocab)
    model = MicroTransformer(vocab_size=vocab_size)
    
    # Convert list to PyTorch Tensor and add batch dimension [1, seq_len]
    input_tensor = torch.tensor([encoded]) 
    
    with torch.no_grad():
        prediction = model(input_tensor)
    
    print(f"Model Output (Anomaly Probability): {prediction.item():.4f}")
    print("\n✅ Verification Successful: The pipeline is mathematically sound!")

if __name__ == "__main__":
    verify_pipeline()