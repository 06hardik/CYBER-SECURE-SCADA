# Computer B (unprotected) startup script
# Receives payload on TCP 9999 and runs it directly.

Set-Location -Path $PSScriptRoot
python .\unprotected_receiver.py
