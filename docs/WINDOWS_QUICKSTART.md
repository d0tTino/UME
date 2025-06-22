# Windows 11 Quickstart

This guide outlines how to set up the development environment on Windows 11.
It walks through enabling WSL, installing the required tools, cloning the
repository and running `codex_setup.sh`.

## Step-by-Step Setup

1. **Enable WSL and install Ubuntu**
   1. Open PowerShell as Administrator and run:
      ```powershell
      wsl --install
      ```
   2. Reboot when prompted and launch the Ubuntu app to create your Linux user.

2. **Install Git**
   - From the Ubuntu terminal:
     ```bash
     sudo apt-get update && sudo apt-get install -y git
     ```
   - Verify Git:
     ```bash
     git --version
     ```

3. **Install Python 3.10 or newer**
   - Download and run the installer from
     [python.org](https://www.python.org/downloads/windows/) making sure to
     check **Add Python to PATH**, or install via
     [winget](https://learn.microsoft.com/windows/package-manager/winget/):
     ```powershell
     winget install --id Python.Python.3.10 -e
     ```
   - Confirm the installation:
     ```powershell
     python --version
     ```

4. **Install Poetry**
   - Use the official installer script:
     ```powershell
     (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
     ```
   - Verify Poetry:
     ```powershell
     poetry --version
     ```

5. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/universal-memory-engine.git
   cd universal-memory-engine
   ```

6. **Run `codex_setup.sh`**
   - From WSL:
     ```bash
     ./codex_setup.sh
     ```
   - Or from PowerShell via WSL:
     ```powershell
     wsl bash ./codex_setup.sh
     ```

7. **Verify the environment**
   ```powershell
   pre-commit run --all-files
   PYTHONPATH=src pytest
   ```

## Docker Desktop Tips

- Enable the **WSL 2 based engine** in Docker Desktop settings.
- Allocate enough memory (4–8 GB recommended) for smoother container builds.
- Verify Docker from a terminal:
  ```powershell
  docker version
  ```
