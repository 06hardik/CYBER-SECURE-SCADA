# CYBER-SECURE-SCADA

Cybersecurity demonstration suite for SCADA/OT environments, built for comparative storytelling between an unprotected baseline and AI-assisted defense workflows.

This repository contains two independent demos that can be run in labs, classrooms, and judge presentations:

- `DEMO-CORRUPTEDHARDWARE/`: behavioral file-access defense using Frida interception and an ONNX model.
- `DEMO-SSHLOGIN/`: command-gating demo with AI inspection and supervisor approval.

## Project Goals

- Show how identical attacker intent behaves differently on unprotected vs protected infrastructure.
- Demonstrate practical defense controls without requiring cloud dependency.
- Provide reproducible runbooks for a 3-machine A/B/C presentation format.

## Demo Summary

| Demo | Core Idea | Baseline Node (B) | Defended Node (C) |
|---|---|---|---|
| Corrupted Hardware | File/payload execution monitoring | Executes received payload directly | Intercepts runtime behavior, classifies actions, may block malicious flow |
| SSH Login | SCADA command submission over client/server flow | Executes critical command immediately | Holds suspicious command and requires supervisor PIN approval |

## Repository Structure

```text
.
├── README.md
├── DEMO-CORRUPTEDHARDWARE/
│   ├── defender_core.py
│   ├── hook.js
│   ├── scada_guard.py
│   ├── launcher.py
│   ├── unprotected_receiver.py
│   ├── demo_payload.py
│   ├── ml/
│   └── scada_root/
└── DEMO-SSHLOGIN/
	├── scada_shell.py
	└── Sovereign_SCADA_AI/
```

## Environment and Prerequisites

Recommended:

- Windows lab machines (PowerShell examples are provided).
- Python 3.9+ for `DEMO-CORRUPTEDHARDWARE`.
- Python 3.13 tested for `DEMO-SSHLOGIN`.
- Isolated Ethernet/LAN for multi-machine demos.

Install dependencies per demo folder.

Corrupted Hardware demo:

```powershell
cd D:\INDIA-INNOVATES\DEMO-CORRUPTEDHARDWARE
python -m pip install -r requirements.txt
```

SSH Login demo:

```powershell
cd D:\INDIA-INNOVATES\DEMO-SSHLOGIN
python -m pip install -r requirements.txt
```

## Demo 1: Corrupted Hardware (Frida + ONNX)

### Concept

A network-delivered payload is sent to both B and C. B executes it directly. C executes under instrumentation, where runtime events are inspected by an ML classifier.

### 3-Machine Topology

- Computer A (Attacker): `192.168.10.1`
- Computer B (Unprotected): `192.168.10.2`
- Computer C (Protected): `192.168.10.3`

### Runbook

Open `DEMO-CORRUPTEDHARDWARE/` on all three systems.

1. Start B receiver:

```powershell
python .\unprotected_receiver.py
```

2. Start C defender:

```powershell
python .\defender_core.py
```

3. Send payload from A:

```powershell
python .\launcher.py --file .\demo_payload.py
```

### Expected Outcome

- B receives `dropped_payload.py` and executes it directly.
- C receives the same payload but routes execution through Frida hooks and `scada_guard` classification.
- C can enforce block/resume behavior based on the model verdict.

### Optional Local Test Mode

```powershell
python .\defender_core.py --script .\simulator.py
```

## Demo 2: SSH Login (Approval-Gated Command Control)

### Concept

Computer A submits SCADA-style commands. Computer B (baseline) executes immediately. Computer C (defended) performs AI inspection and places suspicious commands in a hold state requiring supervisor approval.

### Available Modes (`scada_shell.py`)

- `--mode b-baseline`
- `--mode c-server`
- `--mode a-client`
- `--mode local`

### SCADA Command Language

Grammar:

- `<action> <target>`

Actions:

- `read_temp`
- `check_valve`
- `status_ping`
- `write_firmware`
- `emergency_stop`

Targets:

- `turbine_A`
- `boiler_04`
- `plc_controller`
- `grid_switch`

Common aliases:

- `grid off` -> `write_firmware grid_switch`
- `grid on` -> `status_ping grid_switch`
- `shutdown` -> `write_firmware grid_switch`
- `poweroff` -> `write_firmware grid_switch`

### Runbook

Open `DEMO-SSHLOGIN/` on all involved systems.

1. Computer B (unprotected):

```powershell
python .\scada_shell.py --mode b-baseline
```

2. Computer C (defended server):

```powershell
python .\scada_shell.py --mode c-server --host 0.0.0.0 --port 10051
```

3. Computer A (client targeting C):

```powershell
python .\scada_shell.py --mode a-client --host <C_IP> --port 10051 --actor guest_user
```

### Judge-Friendly Sequence

1. Run `read_temp turbine_A` on both paths.
2. Run `grid off`.
3. Show contrast:
   - B executes immediately.
   - C places command in wait state.
4. Enter wrong PIN on C (rejected), then correct PIN (approved).

Note: current supervisor PIN is defined in `DEMO-SSHLOGIN/scada_shell.py`.

## Safety, Ethics, and Scope

- This repository is for controlled, educational, and defensive demonstration only.
- Use isolated lab networks and demo-only credentials.
- Do not use these scripts against unauthorized systems.
- Rotate or remove demo credentials immediately after presentations.

## Troubleshooting Highlights

Corrupted Hardware demo:

- If payload transfer fails, verify LAN IPs and TCP `9999` reachability.
- Check `logs/events.log` for interception/classification activity.

SSH Login demo:

- If serial output does not toggle, verify COM port and close Arduino Serial Monitor.
- If `serial_backend_ok=False`, reinstall `pyserial==3.5`.
- If A cannot reach C, verify host/port (`10051`) and firewall rules.

## Development Notes

- Generated artifacts, payload drops, and cache/build files are excluded via `.gitignore`.
- Corrupted Hardware model retraining scripts are available under `DEMO-CORRUPTEDHARDWARE/ml/`.

## License

MIT (see demo-specific license files where applicable).
