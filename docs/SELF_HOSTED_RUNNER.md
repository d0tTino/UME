# Configuring a Self-hosted Runner

This project uses GitHub Actions for continuous integration. The default workflow assumes a runner is available with the `self-hosted` label. Follow these steps to provision one, based on GitHub's documentation:

1. **Navigate to your repository's settings.** Under **Actions** > **Runners**, click **Add runner**.
2. **Choose the appropriate operating system** and download the runner package on the machine you want to use.
3. **Extract the archive** and run the `config.sh` script. The setup page will provide a command similar to:
   ```bash
   ./config.sh --url https://github.com/<owner>/<repo> --token <generated-token>
   ```
   Replace `<owner>` and `<repo>` with the repository path and `<generated-token>` with the token provided in the GitHub UI.
4. **Start the runner** using:
   ```bash
   ./run.sh
   ```
   The runner will connect to GitHub and listen for workflow jobs labeled `self-hosted`.

For more details and troubleshooting steps, see the [GitHub Actions documentation](https://docs.github.com/actions/hosting-your-own-runners/about-self-hosted-runners).
