# Contributing to SCADA Guard

Thank you for your interest in contributing to SCADA Guard! This document provides guidelines and instructions for contributing.

## Code of Conduct

Be respectful, inclusive, and professional in all interactions.

## Getting Started

### Prerequisites
- Python 3.9+
- Windows 10/11 or Server 2019+
- Git
- Administrator rights for testing

### Development Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/scada-guard.git
cd scada-guard

# Create a virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Optional: Install dev tools
pip install pylint flake8 black pytest
```

## Workflow

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes:**
   - Keep changes focused and atomic
   - Add comments for complex logic
   - Follow the coding style (see below)

3. **Test thoroughly:**
   ```bash
   # Run unit tests
   pytest tests/

   # Run linting
   flake8 .
   pylint *.py

   # Test integration
   python defender_core.py
   ```

4. **Commit with clear messages:**
   ```bash
   git commit -m "feat: add confidence threshold filtering"
   ```

5. **Push and open a Pull Request:**
   ```bash
   git push origin feature/your-feature-name
   ```

## Coding Style

### Python
- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Max line length: 100 characters
- Use type hints where possible
- Format with `black`:
  ```bash
  black *.py
  ```

### JavaScript (Frida Hooks)
- Use `"use strict";` at the top
- Indent with 4 spaces
- Prefix helper functions with `_`
- Document complex logic with comments

### Docstrings
```python
def classify(hook: str, path: str, bytes_count: int, is_write: bool) -> str:
    """
    Classify a syscall event.
    
    Parameters
    ----------
    hook : str
        Hook name (e.g., 'CreateFileW', 'WriteFile')
    path : str
        File path accessed
    bytes_count : int
        Bytes transferred (for writes)
    is_write : bool
        True if write syscall, False if read
    
    Returns
    -------
    str
        'MALICIOUS' or 'BENIGN'
    """
```

## Areas for Contribution

### High Priority
- [ ] Improve model accuracy (add training data)
- [ ] Optimize inference latency
- [ ] Add more syscall hooks (NtReadFile, etc.)
- [ ] Build Windows Service wrapper
- [ ] Add KQL integration for Azure Sentinel

### Medium Priority
- [ ] Add Linux support
- [ ] Build Docker container
- [ ] Create evaluation benchmarks
- [ ] Add threat intelligence feeds
- [ ] Build web dashboard for log visualization

### Low Priority
- [ ] Documentation improvements
- [ ] Typo fixes
- [ ] Code cleanup
- [ ] GH workflow improvements

## Pull Request Checklist

Before submitting a PR, ensure:

- [ ] Code follows style guide (PEP 8, black)
- [ ] Tests pass locally (`pytest`, `flake8`, `pylint`)
- [ ] Changes don't break existing functionality
- [ ] New dependencies are documented in `requirements.txt`
- [ ] Docstrings and comments are clear
- [ ] Commit messages are descriptive
- [ ] No sensitive data committed (API keys, paths, etc.)
- [ ] `.gitignore` is updated if needed

## Reporting Issues

### Bug Reports
Include:
- Python version
- Windows version
- Steps to reproduce
- Expected behavior
- Actual behavior
- Relevant logs (from `logs/events.log`)

### Feature Requests
Describe:
- Use case
- Proposed solution
- Why it's needed
- Any alternatives considered

## Testing Guidelines

```bash
# Unit tests (if available)
python -m pytest tests/ -v

# Manual integration test
python defender_core.py

# Verify logging
tail -f logs/events.log

# Test standalone modules
python scada_guard.py        # classifier test
python simulator.py          # simulator test
```

## Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

Examples:
```
feat(scada_guard): add confidence threshold filtering
fix(hook): handle null file paths gracefully
docs: update README with Azure Sentinel integration
chore: update dependencies to frida 17.0.0
```

## PR Review Process

1. Maintainer reviews code for:
   - Correctness and logic
   - Performance impact
   - Security implications
   - Test coverage
   - Documentation clarity

2. Feedback is provided via review comments
3. Author addresses feedback and pushes updates
4. Once approved, PR is merged

## Release Process

Releases follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (X.0.0) — Backward-incompatible changes
- **MINOR** (0.X.0) — New features (backward-compatible)
- **PATCH** (0.0.X) — Bug fixes

Release checklist:
1. Update version in `scada_guard.py` docstring
2. Update `CHANGELOG.md`
3. Tag commit: `git tag -a v1.2.3`
4. Push tag: `git push origin v1.2.3`
5. Create GitHub release with changelog

## Recognition

Contributors are recognized in:
- `CONTRIBUTORS.md` (added after first contribution)
- Release notes
- GitHub contributors page

## Questions?

- 📧 Email: support@example.com
- 💬 Discussions: [GitHub Discussions](https://github.com/yourusername/scada-guard/discussions)
- 🐛 Issues: [Report a bug](https://github.com/yourusername/scada-guard/issues)

---

Thank you for contributing to SCADA Guard! 🎉
