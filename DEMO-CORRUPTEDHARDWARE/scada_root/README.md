# SCADA Root Configuration Files

This directory contains mock SCADA system configuration and authentication files used for:
- **Testing** the behavioral defense system
- **Simulating** real SCADA file access patterns
- **Validation** of the ONNX classifier

## Files

### grid_config.txt
Configuration for the electrical power grid model. Contains:
- Substation topology
- Power flow parameters
- Frequency stability thresholds
- Voltage regulation settings

### pressure_thresholds.txt
Safety limits for pressurized systems (pipelines, vessels). Contains:
- Maximum operating pressure (PSI)
- Emergency shutdown pressure
- Pressure relief valve setpoints

### safety_limits.txt
Industrial system safety parameters. Contains:
- Temperature limits
- Flow rate limits
- Alarm thresholds
- Emergency stop triggers

### turbine_auth.csv
Authentication and permissions for turbine control systems. Contains:
- Operator IDs
- Role-based access control (RBAC)
- SSH keys and certificates
- API authentication tokens

## Usage

These files are benign test data. The simulator reads them without modification during testing:

```python
from simulator import simulate_reads

simulate_reads()  # Reads all files in SCADA_ROOT
```

Output:
```
[SIM] READ  C:\SCADA_ROOT\grid_config.txt       (2048 bytes)
[SIM] READ  C:\SCADA_ROOT\pressure_thresholds.txt (512 bytes)
[SIM] READ  C:\SCADA_ROOT\safety_limits.txt     (1024 bytes)
[SIM] READ  C:\SCADA_ROOT\turbine_auth.csv      (4096 bytes)
```

## Security Notes

⚠️ **Do NOT** place actual credentials in these files  
⚠️ **Test data only** — Never deploy with real SCADA configs  
✅ **Safe to read** — Simulator only opens files for reading  
✅ **Non-destructive** — No files are modified or deleted  

---

**For more info, see [README.md](../README.md)**
