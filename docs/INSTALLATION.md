# Module 1 Installation

## Purpose

Module 1 creates a reproducible Python 3.12 development environment and performs read-only
checks of Git, repository configuration, and EnergyPlus 26.1.0. It does not run an EnergyPlus
simulation, copy an IDF, install Ollama, or implement later modules.

## Supported setups

### Windows 11 native

Install Git, Python 3.12, and EnergyPlus 26.1.0 using their official installers. A typical
EnergyPlus location is `C:\EnergyPlusV26-1-0`, but use the actual installation location.
Open PowerShell in the repository and verify:

```powershell
git --version
py -3.12 --version
.\scripts\bootstrap_windows.ps1
```

If PowerShell blocks the script, use a process-only policy:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\bootstrap_windows.ps1
```

This does not require administrator privileges or change the permanent policy.

### Windows 10 with WSL2 Ubuntu 24.04

Install Git, Python 3.12 with `venv`, and EnergyPlus 26.1.0 in WSL using official product
instructions. OS and EnergyPlus installation are intentionally outside the bootstrap script.
A typical location is `/usr/local/EnergyPlus-26-1-0`; confirm the real location.

```bash
git --version
python3 --version
bash scripts/bootstrap_wsl.sh
```

Keep Linux paths in the WSL `.env`; do not use a Windows `C:\...` path there.

## VS Code

Install VS Code with the Microsoft Python and Pylance extensions. For WSL, also install the
WSL extension and open the repository in WSL. Select `.venv\Scripts\python.exe` on Windows or
`.venv/bin/python` in WSL.

## Manual setup

Windows:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

WSL:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

Copy `.env.example` only when `.env` is absent. Set `ENERGYPLUS_HOME` to the installation
directory, not the executable. Native Windows commonly uses `C:\EnergyPlusV26-1-0`; WSL
commonly uses `/usr/local/EnergyPlus-26-1-0`. `.env` is ignored by Git.

## Verification

With the virtual environment active:

```text
python scripts/check_environment.py
python -m pytest
python -m ruff check .
python -m mypy
```

The checker invokes only `energyplus --version`; it never passes an IDF or weather file and
never starts a building simulation. Its exit code is zero only when all required checks pass.
Missing `WeatherData` is an optional warning.

## Common errors

- **PowerShell execution policy:** use the process-only command above or the manual steps.
- **Wrong Python selected:** `python --version` must report 3.12.x. Activate or recreate
  `.venv`, then select it in VS Code.
- **`ENERGYPLUS_HOME` missing:** create `.env`, set the real installation directory, and rerun.
- **Wrong EnergyPlus version:** configure EnergyPlus 26.1.0; output must contain `26.1`.
- **`pyenergyplus` import failure:** confirm `ENERGYPLUS_HOME/pyenergyplus` exists and the
  installation is complete.
- **Missing example:** confirm `ExampleFiles/5ZoneAirCooled.idf` exists under the installation.
  Do not copy it during Module 1.
- **WSL path confusion:** `/mnt/c/...` is WSL's view of Windows. A Linux EnergyPlus install uses
  a Linux path and executable; native Windows uses `energyplus.exe`.
- **Git not found:** install Git outside the bootstrap script and reopen the terminal.

