# Security Policy

## Reporting a Vulnerability

**Do NOT open a public GitHub issue for security vulnerabilities.**

If you discover a security vulnerability in SCADA Guard, please email:
**security@example.com**

Include:
- Description of vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if available)

Your report will be reviewed within 48 hours.

## Security Considerations for SCADA Guard

### By Design

✅ **Fail-safe defaults** — Defaults to MALICIOUS classification on any error  
✅ **Offline inference** — No network connectivity; no data leaves your system  
✅ **Read-only monitoring** — Never modifies monitored files  
✅ **Audit logging** — All decisions logged for compliance/forensics  
✅ **Windows-native hooks** — Uses OS-level kernel hooks via Frida  

### Best Practices for Deployment

1. **Run as Administrator** — Frida instrumentation requires elevated privileges
2. **Isolate the monitoring system** — Run on dedicated or air-gapped machines
3. **Secure log files** — Restrict read/write access to `logs/events.log`
4. **Monitor the monitor** — Log all scada_guard.py modifications
5. **Keep Python updated** — Apply security patches for Python runtime
6. **Verify ONNX model integrity** — Hash `scada_guard.onnx` on deployment
7. **Test before production** — Validate on staging systems first
8. **Backup configurations** — Store safe copies of `scada_root/` configs

### Known Limitations

⚠️ **Windows-only** — Currently supports Windows 10/11 and Server 2019+  
⚠️ **Single-threaded hooking** — I/O bound; max ~1000 events/sec per core  
⚠️ **ML model constraints** — Trained on specific SCADA patterns; may not generalize  
⚠️ **Frida library trust** — Depends on Frida's security for hook integrity  

### Threat Model

**Protected Against:**
- Unauthorized file writes to SCADA configs
- Lateral movement via file exfiltration
- Privilege escalation via temp file hijacking
- Ransomware file encryption patterns

**NOT Protected Against:**
- Kernel-level rootkits (operate below Frida)
- Memory corruption exploits
- Hypervisor attacks
- Physical tampering

### Compliance

SCADA Guard helps meet security baselines for:
- **NERC CIP** — Behavioral monitoring for Industrial Control Systems
- **IEC 62351** — Power system information security standards
- **ISO 27001** — Information security management (Annex A.12)
- **HIPAA/PCI-DSS** — Audit trail requirements (via logging)

## Security Update Policy

- **Critical fixes:** Released immediately with advisories
- **High/Medium fixes:** Released as patch versions (e.g., 1.0.1)
- **Low fixes:** Batched into next minor release

Subscribe to GitHub security advisories:
https://github.com/yourusername/scada-guard/security

---

**Last Updated:** March 22, 2026  
**Contact:** security@example.com
