# SCADA Guard

Real-time SCADA file access monitoring using Frida + ML model.

## Setup

```bash
pip install -r requirements.txt
python defender_core.py
```

Check `logs/events.log` for results.

## Network-Triggered Update (March 2026)

The input source was extended from local-only execution to optional network delivery, while keeping the Frida interception and ML decision pipeline unchanged.

### What changed

- Added `receive_payload()` in `defender_core.py`
	- Listens on TCP `0.0.0.0:9999`
	- Receives raw file bytes
	- Saves payload as `dropped_payload.py`
	- Returns the saved path for execution
- Updated `Defender.__init__` to accept optional `script_path`
	- If `--script` is provided: runs provided script path (existing behavior)
	- If `--script` is omitted: waits for network payload, then runs `dropped_payload.py`
- Added `launcher.py`
	- Minimal sender that transmits a local file to the defender listener

### What stayed unchanged

- Frida spawn/attach/resume flow
- `hook.js` injection and message transport
- `_on_message()` event handling
- `scada_guard.classify(hook, path, bytes, is_write)` call
- Kill/resume enforcement logic
- Logging behavior

### 3-machine demo architecture (Ethernet LAN)

- Computer A (Attacker): `192.168.10.1`
- Computer B (Unprotected): `192.168.10.2`
- Computer C (Protected): `192.168.10.3`

All hosts listen on TCP `9999` for payload delivery.

### Run order

Computer B (unprotected receiver):

```bash
python unprotected_receiver.py
```

Computer C (protected receiver + defender pipeline):

```bash
python defender_core.py
```

Computer A (send same payload to both B and C):

```bash
python launcher.py --file demo_payload.py
```

Default launcher targets are `192.168.10.2,192.168.10.3`.

### Network behavior by host

- B receives `dropped_payload.py` and executes it directly via `python dropped_payload.py`.
- C receives `dropped_payload.py`, then runs it through existing Frida interception and ML classification flow.
- Same payload, different outcome: B is unprotected, C can block malicious behavior.

### Included demo scripts

- `launcher.py` — attacker sender for one or many IP targets
- `unprotected_receiver.py` — B-side listener + direct execution
- `run_unprotected_b.ps1` — one-command startup for B
- `demo_payload.py` — safe simulation payload (SCADA write simulation + exfil simulation)

### Repository hygiene

- Generated payload/build artifacts are ignored (`dropped_payload.py`, `simulator/`, `*.toc`, `*.pkg`, `*.pyz`, logs/cache).
- Demo GitHub Actions test workflow has been removed.

### Optional local mode (unchanged)

```bash
python defender_core.py --script simulator.py
```

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
