# DEMO-SSHLOGIN: A/B/C SCADA Cyber Defense Demo

This folder contains a complete live demo for three-machine storytelling:

- Computer A: attacker/operator terminal
- Computer B: unprotected baseline node
- Computer C: AI-defended node with supervisor approval gate

## What this demo proves

1. Same attacker command can impact unprotected infrastructure (B) immediately.
2. The defended node (C) intercepts malicious intent, holds command execution, and requires supervisor approval.
3. Approval is entered only on Computer C, not on attacker terminal A.

## Components

- `scada_shell.py`
- `Sovereign_SCADA_AI/` (custom tokenizer/model/training assets)
- `requirements.txt`

`scada_shell.py` modes:

- `--mode b-baseline`: Computer B (no protection)
- `--mode c-server`: Computer C approval + AI inspection console
- `--mode a-client`: Computer A simple operator terminal
- `--mode local`: local single-terminal test mode

## Requirements

Install from this folder:

```powershell
D:
cd D:\INDIA-INNOVATES\DEMO-SSHLOGIN
C:/Python313/python.exe -m pip install -r requirements.txt
```

If serial backend is broken, repair with:

```powershell
C:/Python313/python.exe -m pip uninstall -y serial
C:/Python313/python.exe -m pip install --force-reinstall --no-cache-dir pyserial==3.5
```

## SCADA command language

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

Aliases:

- `grid off` -> `write_firmware grid_switch`
- `grid on` -> `status_ping grid_switch`
- `shutdown` -> `write_firmware grid_switch`
- `poweroff` -> `write_firmware grid_switch`

## Supervisor approval

Current supervisor PIN in code: `9988`

File: `DEMO-SSHLOGIN/scada_shell.py`

## Legitimate SSH lab setup (A -> B and A -> C)

Use dedicated demo users; do not use stolen credentials.

On Computer B and C (Windows):

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
New-NetFirewallRule -Name sshd_demo -DisplayName "OpenSSH Demo" -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22
```

Create demo users:

```powershell
net user scada_b DemoPass!234 /add
net user scada_c DemoPass!234 /add
```

From Computer A:

```powershell
ssh scada_b@<B_IP>
ssh scada_c@<C_IP>
```

## Runbook

### 1. Computer B (unprotected)

In B session:

```powershell
D:
cd D:\INDIA-INNOVATES\DEMO-SSHLOGIN
python .\scada_shell.py --mode b-baseline
```

### 2. Computer C (defended)

In C local console:

```powershell
D:
cd D:\INDIA-INNOVATES\DEMO-SSHLOGIN
python .\scada_shell.py --mode c-server --host 0.0.0.0 --port 10051
```

### 3. Computer A (attacker UI)

To target C:

```powershell
D:
cd D:\INDIA-INNOVATES\DEMO-SSHLOGIN
python .\scada_shell.py --mode a-client --host <C_IP> --port 10051 --actor guest_user
```

To target B directly, use the B SSH session and run commands there (no hold/approval flow).

## Judge demo script (recommended)

1. Start with harmless command on both nodes:
- `read_temp turbine_A`

Expected:
- B: executes immediately
- C path via A: executes immediately

2. Attack command:
- `grid off`

Expected on B:
- Executes immediately
- Arduino OFF signal sent without gate

Expected on C path:
- A shows: `Command in wait for approval on Computer C...`
- C shows AI inspection, anomaly verdict, and hold panel
- Wrong PIN on C -> A shows rejected
- Correct PIN (`9988`) on C -> A shows approved/executed

## Troubleshooting

1. Light does not toggle:
- Verify `Arduino connected on COM8 @ 9600 baud.` appears on B/C shell startup.
- Ensure Arduino IDE Serial Monitor is closed.
- Confirm correct COM port in `ARDUINO_PORT`.
- Confirm sketch expects `'0'` and `'1'` bytes.

2. `serial_backend_ok=False`:
- Run pyserial repair commands above.

3. A client cannot connect C:
- Check C IP and port `10051`
- Confirm firewall allows `10051`
- Ensure `c-server` is running first

## Security note

This is a controlled lab demo. Keep SSH users isolated to demo machines and rotate/remove demo credentials after presentation.
