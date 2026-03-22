# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- First public release

### Changed
- Initial implementation

### Deprecated

### Removed

### Fixed

### Security

## [1.0.0] - 2026-03-22

### Added
- Initial SCADA Guard release
- Frida-based behavioral hooking for syscall interception
- **Custom micro-transformer model** for file access classification (~120K params, <2ms inference)
- **ML training pipeline** with PyTorch
  - Synthetic data generator (10K+ samples)
  - Path tokenizer with learned vocabulary
  - Transformer architecture (2 layers, 4 heads)
  - ONNX export for production inference
  - Comprehensive evaluation metrics
- Real-time logging to `logs/events.log`
- Support for CreateFileW, CreateFileA, NtCreateFile, WriteFile, NtWriteFile hooks
- Confidence scoring for predictions
- Non-destructive simulator for testing
- Comprehensive documentation (README, DEVELOPMENT, ML/README guides)

### Dependencies
**Production:**
- frida>=16.0.0
- rich>=13.0.0
- onnxruntime>=1.18.0
- pyinstaller>=6.0.0 (optional)

**Model Training (Optional):**
- torch>=2.2.0
- onnx>=1.16.0
- numpy>=1.26.0

---

## Release Notes

### Latest Features
- ✅ Sub-2ms ONNX inference latency
- ✅ SCADA-specific threat detection
- ✅ Offline, network-free operation
- ✅ Fail-safe defaults (block on error)
- ✅ Detailed event logging and audit trail

---

**For questions or bug reports, see [CONTRIBUTING.md](CONTRIBUTING.md)**
