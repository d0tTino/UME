from datetime import datetime

from ume.models import create_decision_analysis


def test_create_decision_analysis_sets_created_at() -> None:
    before = datetime.utcnow()
    analysis = create_decision_analysis("how many decisions?")
    assert analysis.query == "how many decisions?"
    assert analysis.analysis_id
    assert analysis.created_at >= before
    assert analysis.created_at <= datetime.utcnow()
