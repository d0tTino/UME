from __future__ import annotations

import sys

from ume.plugins.registry import clear_plugins, register_plugin


class _Dummy:
    pass


def test_plugins_subcommand_outputs_registered_plugins(capsys, monkeypatch) -> None:
    clear_plugins()
    register_plugin("integration_adapter", "dummy", _Dummy)
    monkeypatch.setattr(sys, "argv", ["ume_cli.py", "plugins", "--capability", "integration_adapter"])

    from ume_cli import main

    main()
    captured = capsys.readouterr()
    assert '"capability": "integration_adapter"' in captured.out
    assert '"name": "dummy"' in captured.out
