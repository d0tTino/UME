from ume.models import create_proposed_action


def test_create_proposed_action_defaults() -> None:
    action = create_proposed_action("take a nap")
    assert action.description == "take a nap"
    assert action.action_id
    assert action.rank == 0
    assert action.is_optimal is False
    assert action.outcome_metrics == {}
