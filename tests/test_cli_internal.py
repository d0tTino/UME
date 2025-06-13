from ume_cli import UMEPrompt, _setup_warnings


def test_umeprompt_commands(tmp_path):
    prompt = UMEPrompt()
    prompt.do_new_node('n1 "{}"')
    prompt.do_new_node('n2 "{}"')
    prompt.do_new_edge('n1 n2 L')
    assert set(prompt.graph.get_all_node_ids()) == {"n1", "n2"}
    assert ("n1", "n2", "L") in prompt.graph.get_all_edges()

    snap = tmp_path / "snap.json"
    prompt.do_snapshot_save(str(snap))
    assert snap.is_file()

    prompt.do_del_edge('n1 n2 L')
    assert prompt.graph.get_all_edges() == []

    prompt.do_redact_node('n1')
    assert prompt.graph.get_node('n1') is None

    prompt.do_clear('')
    assert prompt.graph.get_all_node_ids() == []

    prompt.do_snapshot_load(str(snap))
    assert set(prompt.graph.get_all_node_ids()) == {"n1", "n2"}

    # exercise query and audit related commands
    prompt.do_show_nodes("")
    prompt.do_show_edges("")
    prompt.do_neighbors("n1")
    prompt.do_show_audit("")

    _setup_warnings(True, str(tmp_path / "warn.log"))
    prompt.do_exit("")
