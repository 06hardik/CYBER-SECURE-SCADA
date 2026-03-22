# SCADA Guard

Real-time SCADA file access monitoring using Frida + ML model.

## Setup

```bash
pip install -r requirements.txt
python defender_core.py
```

Check `logs/events.log` for results.

## Quick Test

```bash
python scada_guard.py      # Test classifier
python simulator.py        # Test file access simulation
```


## Project Structure

```
.
├── defender_core.py    # Main orchestrator
├── hook.js            # Frida hook script
├── scada_guard.py     # ONNX classifier
├── simulator.py       # Test simulator
├── ml/                # Training code
│   ├── train.py
│   ├── evaluate.py
│   ├── model.py
│   ├── dataset.py
│   ├── data_gen.py
│   └── tokeniser.py
└── scada_root/        # Test configs
```

## Config

Edit the core files directly:

- **simulator.py**: `SCADA_ROOT` path
- **defender_core.py**: `DEFAULT_PYTHON`, `LOG_DIR`
- **hook.js**: `shouldSkip()` function for filtering

## API

```python
from scada_guard import classify_with_confidence

verdict, conf = classify_with_confidence("WriteFile", r"C:\file.txt", 1024, True)
# Returns: ("MALICIOUS", 0.95)
```

## Retrain the Model

```bash
pip install -r ml/requirements_ml.txt
cd ml

python data_gen.py       # Generate training data
python tokeniser.py      # Build vocabulary
python train.py          # Train & export ONNX
python evaluate.py       # Test it
```

Model saves to `../scada_guard.onnx`.

## Model Info

- Micro-transformer (2 layers, 4 heads, ~120K params)
- Input: Tokenized file paths + 7 features
- Output: BENIGN or MALICIOUS
- Speed: <2ms/event on CPU

## Dependencies

**Production:**
```
frida>=16.0.0
rich>=13.0.0
onnxruntime>=1.18.0
```

**Training:**
```
torch>=2.2.0
onnx>=1.16.0
numpy>=1.26.0
```

## Build Exe

```bash
pip install pyinstaller
pyinstaller --onefile defender_core.py
```

Output: `dist/defender_core.exe`

## License

MIT
