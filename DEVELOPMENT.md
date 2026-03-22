# Development Guide

Complete guide for setting up SCADA Guard development environment.

## Prerequisites

- Windows 10/11 or Server 2019+
- Python 3.9 or higher
- Git
- Administrator privileges (for Frida testing)
- Visual Studio Build Tools (optional, for C++ dependencies)

## Environment Setup

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/scada-guard.git
cd scada-guard
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Or (PowerShell)
.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```bash
# Core dependencies
pip install -r requirements.txt

# Development dependencies
pip install -e ".[dev]"

# OR manually
pip install \
    pytest \
    pytest-cov \
    pylint \
    flake8 \
    black \
    pyinstaller
```

### 4. Verify Installation

```bash
# Check imports
python -c "import frida; print(frida.__version__)"
python -c "import onnxruntime; print(onnxruntime.__version__)"
python -c "from rich.console import Console"

# Run tests
python scada_guard.py
python simulator.py
```

## Project Structure

```
scada-guard/
├── .github/
│   ├── workflows/
│   │   └── tests.yml              # CI/CD pipeline
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   └── pull_request_template.md
├── scada_root/                    # Test data directory
│   └── *.txt, *.csv              # SCADA config files
├── logs/                          # Generated at runtime
│   └── events.log                # Event logs
├── defender_core.py              # Main orchestrator
├── hook.js                        # Frida hook script
├── scada_guard.py                # ONNX classifier
├── simulator.py                  # File access simulator
├── requirements.txt              # Runtime dependencies
├── pyproject.toml               # Package metadata & tool config
├── .editorconfig                # Code style settings
├── .gitignore                   # Git ignore rules
├── README.md                    # User documentation
├── CONTRIBUTING.md             # Contribution guidelines
├── DEVELOPMENT.md              # This file
├── SECURITY.md                 # Security policies
├── CHANGELOG.md                # Release notes
└── LICENSE                     # MIT License
```

## Code Style & Quality

### PEP 8 Compliance

```bash
# Format code with black
black *.py

# Check formatting without changes
black --check *.py

# Lint with flake8
flake8 . --count --max-line-length=100

# Deep analysis with pylint
pylint *.py --max-line-length=100
```

### Auto-format on Save

#### VS Code
Add to `.vscode/settings.json`:
```json
{
    "[python]": {
        "editor.formatOnSave": true,
        "editor.defaultFormatter": "ms-python.black-formatter",
        "editor.codeActionsOnSave": {
            "source.organizeImports": "explicit"
        }
    }
}
```

#### PyCharm
Settings → Editor → Code Style → Python → Scheme → Set to "Black"

## Testing

### Unit Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html

# Run specific test file
pytest tests/test_classifier.py -v
```

### Integration Tests

```bash
# Test ONNX classifier
python scada_guard.py

# Expected output:
# ✓ grid_config.txt (BENIGN)
# ✓ turbine_auth.csv (BENIGN)
# ✓ safety_limits.txt (MALICIOUS)
```

### Manual Testing

```bash
# Run with custom Python interpreter
python defender_core.py --python "C:\Python313\python.exe"

# Monitor in another terminal
type logs\events.log              # Show logs

# Or tail the file (PowerShell)
Get-Content logs\events.log -Tail 10 -Wait
```

## Building Artifacts

### Standalone Executable

```bash
# Build single-file executable
pyinstaller --onefile defender_core.py

# Output: dist/defender_core.exe

# Test executable
dist\defender_core.exe
```

### Python Package

```bash
# Build distribution
python -m build

# Optional: Install in development mode
pip install -e .
```

## Debugging

### Enable Verbose Logging

Edit `defender_core.py`:
```python
# Add near top of file
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Debug Frida Hooks

Edit `hook.js`:
```javascript
// Add console logging
console.log("[DEBUG] Processing path: " + path);
console.log("[DEBUG] Verdict: " + verdict);
```

### Inspect ONNX Model

```python
import onnxruntime as ort

# Load and inspect
session = ort.InferenceSession("scada_guard.onnx")

# Get input/output names
for input in session.get_inputs():
    print(f"Input: {input.name}, Shape: {input.shape}, Type: {input.type}")

for output in session.get_outputs():
    print(f"Output: {output.name}, Shape: {output.shape}, Type: {output.type}")
```

## Common Issues

### Issue: `onnxruntime` not installed
```bash
pip install onnxruntime
```

### Issue: Frida attach fails
```bash
# Run as Administrator (PowerShell)
start-process powershell -verb runas
python defender_core.py
```

### Issue: `vocab.json` not found
```bash
# Build vocabulary (requires training data pipeline)
cd ml
python data_gen.py
python tokeniser.py
```

### Issue: Python interpreter not found
```bash
# Specify explicit path
python defender_core.py --python "C:\Path\To\python.exe"

# Or set environment variable
$env:PYTHON_EXE = "C:\Python313\python.exe"
python defender_core.py
```

## Performance Profiling

### Profile Inference Speed

```python
import time
from scada_guard import classify

# Warm up
classify("CreateFileW", r"C:\test.txt", 0, False)

# Profile
start = time.perf_counter()
for _ in range(1000):
    classify("CreateFileW", r"C:\SCADA_ROOT\grid_config.txt", 0, False)
elapsed = time.perf_counter() - start

print(f"1000 inferences in {elapsed:.3f}s = {1000/elapsed:.0f} ops/sec")
# Expected: ~500-2000 ops/sec per core
```

### Memory Usage

```bash
# Monitor with psutil
pip install psutil

python -c "
import psutil
import os
from scada_guard import classify_with_confidence

proc = psutil.Process(os.getpid())
for i in range(100):
    classify_with_confidence('CreateFileW', f'C:\\test_{i}.txt', 0, False)
    if i % 10 == 0:
        mem = proc.memory_info()
        print(f'Iteration {i}: {mem.rss / 1024 / 1024:.1f} MB')
"
```

## Release Process

### Pre-Release Checklist

- [ ] Update `CHANGELOG.md`
- [ ] Update version in docstrings
- [ ] Run full test suite: `pytest tests/ -v`
- [ ] Verify imports work: `python scada_guard.py`
- [ ] Build executable: `pyinstaller --onefile defender_core.py`
- [ ] Update `pyproject.toml` version
- [ ] Run QA tests

### Create Release

```bash
# Tag release
git tag -a v1.0.0 -m "Release SCADA Guard v1.0.0"

# Push tag (triggers CI/CD)
git push origin v1.0.0

# Create GitHub release with changelog
# https://github.com/yourusername/scada-guard/releases/new
```

## Documentation

### Generate HTML Docs

```bash
# Install sphinx (optional)
pip install sphinx sphinx-rtd-theme

# Build docs (if docs/ directory exists)
cd docs && make html
```

### Update README

- Keep README.md synchronous with code
- Update examples when APIs change
- Verify all links work
- Keep architecture diagrams current

## Git Workflow

### Branch Naming

```bash
feature/add-azure-sentinel-integration
bugfix/fix-null-path-handling
docs/update-installation-guide
chore/upgrade-dependencies
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(classifier): add confidence threshold filtering
^--^  ^--------^  ^---------------------------^
|     |           |
|     |           +─→ Description
|     +─────────────→ Scope (optional)
+─────────────────→ Type: feat, fix, docs, style, refactor, perf, test, chore
```

### Pre-commit Hook

```bash
# Install pre-commit framework
pip install pre-commit

# Configure
cat > .pre-commit-config.yaml << EOF
repos:
  - repo: https://github.com/psf/black
    rev: 23.1.0
    hooks:
      - id: black
  - repo: https://github.com/PyCQA/flake8
    rev: 5.0.4
    hooks:
      - id: flake8
        args: [--max-line-length=100]
EOF

# Install hooks
pre-commit install

# Test
pre-commit run --all-files
```

## Resources

- [Frida Documentation](https://frida.re/)
- [ONNX Runtime](https://onnxruntime.ai/)
- [Python Security](https://python-security.readthedocs.io/)
- [SCADA Security](https://www.cisa.gov/scada-security)

## Support

- 📧 Email: support@example.com
- 💬 Discussions: GitHub Discussions
- 🐛 Issues: GitHub Issues

---

Happy developing! 🚀
