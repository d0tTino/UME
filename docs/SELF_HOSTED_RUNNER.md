# Self-Hosted GitHub Runner Setup

This guide explains how to configure a self-hosted runner for UME's GitHub Actions workflows.

## Prerequisites

* A machine running a recent Linux distribution
* `python3` and `pip` installed
* Ability to install required dependencies (Docker is recommended but not required)
* Access to the repository's "Settings" tab with permission to create self-hosted runners

## Steps

1. **Register the runner**
   1. Navigate to **Settings → Actions → Runners** in this repository on GitHub.
   2. Click **New self-hosted runner** and choose **Linux** as the operating system.
   3. Follow the displayed instructions to download the runner package and run the registration script. The commands resemble:
      ```bash
      mkdir actions-runner && cd actions-runner
      curl -O -L https://github.com/actions/runner/releases/download/v2.314.1/actions-runner-linux-x64-2.314.1.tar.gz
      tar xzf actions-runner-linux-x64-2.314.1.tar.gz
      ./config.sh --url https://github.com/your-org/universal-memory-engine --token <TOKEN>
      ```
   4. When prompted, give the runner a descriptive name (e.g., `ume-self-hosted-1`).

2. **Install dependencies**
   The runner should have `python3`, `poetry`, and any other system packages required by the project. You can reuse the commands from the CI workflow:
   ```bash
   sudo apt-get update && sudo apt-get install -y python3 python3-pip
   python3 -m pip install --upgrade pip
   python3 -m pip install poetry
   ```

3. **Run the runner service**
   Start the runner interactively with:
   ```bash
   ./run.sh
   ```
   For a background service, use the provided service installation script:
   ```bash
   sudo ./svc.sh install
   sudo ./svc.sh start
   ```

4. **Verify**
   After the service starts, the GitHub UI should show the runner online under the **Runners** tab. Jobs that specify the `self-hosted` label will now execute on this machine.

For more details, refer to [GitHub's documentation on self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners/about-self-hosted-runners).
