import subprocess
from pathlib import Path
import shutil
import pytest

def test_detect_secrets_hook_blocks(tmp_path):
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("AWS_SECRET_ACCESS_KEY=abcd1234")

    if shutil.which("pre-commit") is None:
        pytest.skip("pre-commit not installed")
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["pre-commit", "run", "detect-secrets", "--files", str(secret_file)],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
