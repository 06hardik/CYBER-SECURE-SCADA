---
description: "Design or refine a dual-terminal SCADA demo with attacker UI on Computer A and AI approval console on Computer C"
name: "SCADA Dual-Terminal Demo"
argument-hint: "Describe your current SCADA shell setup and what you want to improve"
agent: "agent"
---
Create or improve a SCADA demo architecture with two distinct terminal experiences:

- Computer A (attacker/operator terminal): simple command UI, no AI internals
- Computer C (defense console): real-time AI inspection, malicious-command hold, and supervisor approval prompt

Requirements:
1. Preserve existing model inference and command classification logic unless the user explicitly asks to retrain or change thresholds.
2. Use a clear command protocol between A and C so A can receive status transitions: `ok`, `hold`, `approved`, `rejected`.
3. Ensure only Computer C can approve held commands.
4. Keep command language aligned to trained SCADA grammar and vocabulary.
5. Add judge-friendly terminal UX on C (readable risk context, score, verdict, hold/release state).
6. Keep A terminal minimal and operationally clean.

Output format:
1. Architecture summary (A flow, C flow, message protocol)
2. Exact file changes with paths
3. Run instructions for both machines
4. Demo script (safe command, malicious command, approval/rejection outcomes)
5. Risks and hardening checklist (auth, encryption, logging, replay protection)

When user asks about SSH credentials, provide only legitimate lab setup guidance (creating test user/keys, enabling OpenSSH, firewall rules) and do not provide credential theft instructions.
