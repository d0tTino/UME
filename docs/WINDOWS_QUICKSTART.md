# Windows 11 Quickstart

This guide outlines how to set up the development environment on Windows 11.
It covers installing Python and Poetry, a few Docker Desktop tips, and running
`codex_setup.sh` either from WSL or PowerShell.

## Installing Python and Poetry

1. **Python 3.10 or newer**
   - Download and run the official installer from
     [python.org](https://www.python.org/downloads/windows/). Make sure to check
     **Add Python to PATH** during installation.
   - Alternatively, you can install via [winget](https://learn.microsoft.com/windows/package-manager/winget/):
     ```powershell
     winget install --id Python.Python.3.10 -e
     ```
   - Verify the installation:
     ```powershell
     python --version
     ```

2. **Poetry**
   - Install using the official installer script:
     ```powershell
     (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
     ```
   - After installation, ensure `poetry` is available in your terminal:
     ```powershell
     poetry --version
     ```

## Docker Desktop Hints

- Enable the **WSL 2 based engine** in Docker Desktop settings.
- Allocate enough memory (4–8 GB recommended) for smoother container builds.
- Verify Docker from a terminal:
  ```powershell
  docker version
  ```

## Running `codex_setup.sh`

The setup script assumes a Unix-like environment.
You can run it in two ways on Windows:

1. **Using WSL**
   - Open your WSL terminal and navigate to the repository root.
   - Execute:
     ```bash
     ./codex_setup.sh
     ```

2. **From PowerShell via WSL**
   - If you prefer staying in PowerShell, invoke the script through WSL:
     ```powershell
     wsl bash ./codex_setup.sh
     ```

After the script completes, you can verify the environment with:
```powershell
pre-commit run --all-files
PYTHONPATH=src pytest
```
