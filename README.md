# CYBER-SECURE-SCADA

Offline SCADA cybersecurity demos for the India Innovates project.

## Repository Layout

- `DEMO-CORRUPTEDHARDWARE/` : Frida + ONNX behavioral defense demo with network-triggered payload delivery.
- `DEMO-SSHLOGIN/` : SSH/login behavior simulation demo.

## Corrupted Hardware Demo (3 Machines)

Use static Ethernet LAN addresses:

- Computer A (Attacker): `192.168.10.1`
- Computer B (Unprotected): `192.168.10.2`
- Computer C (Protected): `192.168.10.3`

From `DEMO-CORRUPTEDHARDWARE/`:

1. On Computer B:

```bash
python unprotected_receiver.py
```

2. On Computer C:

```bash
python defender_core.py
```

3. On Computer A:

```bash
python launcher.py --file demo_payload.py
```

Expected behavior:

- B runs payload directly without inspection.
- C runs payload through existing Frida interception + ONNX classification and can block malicious behavior.

## Notes

- Generated artifacts (build/dist/cache, dropped payloads, simulator build files, logs) are ignored via `.gitignore`.
- GitHub Actions test workflow for the corrupted hardware demo has been removed as requested.
