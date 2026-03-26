import torch
import json
from tokenizer import SCADATokenizer
from model import MicroTransformer

# 1. Setup
tokenizer = SCADATokenizer()
with open("vocab.json", "r") as f:
    tokenizer.vocab = json.load(f)

vocab_size = len(tokenizer.vocab)
model = MicroTransformer(vocab_size=vocab_size)
model.load_state_dict(torch.load("scada_model.pth"))
model.eval()

def check_log(log_text):
    encoded = torch.tensor([tokenizer.encode(log_text)])
    with torch.no_grad():
        prediction = model(encoded).item()
    
    status = "🚨 ANOMALY DETECTED" if prediction > 0.5 else "✅ NORMAL"
    print(f"Log: {log_text}")
    print(f"Confidence: {prediction:.4f} | Result: {status}\n")

# 2. Test it out!
if __name__ == "__main__":
    print("--- SCADA Sovereign AI Live Test ---\n")
    check_log("[09:00] USER: admin_01 ACTION: read_temp TARGET: turbine_A")
    check_log("[03:00] USER: guest_user ACTION: write_firmware TARGET: plc_controller")