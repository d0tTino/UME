from ume.models import create_proposed_action


def test_create_proposed_action_defaults() -> None:
    action = create_proposed_action("take a nap")
    assert action.description == "take a nap"
    assert action.action_id
    assert action.rank == 0
    assert action.is_optimal is False
    assert action.outcome_metrics == {}
    assert action.schema_version == "3.0.0"


def test_create_proposed_action_custom_values() -> None:
    metrics = {"accuracy": 0.95, "speed": 1.2}
    action = create_proposed_action(
        "run tests",
        rank=1,
        is_optimal=True,
        outcome_metrics=metrics,
    )
    assert action.rank == 1
    assert action.is_optimal is True
    assert action.outcome_metrics == metrics
