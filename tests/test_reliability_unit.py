from ume import reliability


def test_score_text_edge_cases(monkeypatch):
    class DummyLang:
        def __init__(self, prob):
            self.prob = prob

    def fake_detect(text):
        if not text or text.isdigit():
            raise reliability.LangDetectException('empty', 'empty')
        return [DummyLang(0.8)]

    monkeypatch.setattr(reliability, 'detect_langs', fake_detect)

    assert reliability.score_text('') == 0.0
    assert reliability.score_text('123') == 0.0
    assert reliability.score_text('abc123') == 0.4


def test_filter_low_confidence_metrics(monkeypatch):
    class DummyHist:
        def __init__(self):
            self.values = []
        def observe(self, val):
            self.values.append(val)
    class DummyCounter:
        def __init__(self):
            self.count = 0
        def inc(self):
            self.count += 1

    hist = DummyHist()
    counter = DummyCounter()
    monkeypatch.setattr(reliability, 'RESPONSE_CONFIDENCE', hist)
    monkeypatch.setattr(reliability, 'FALSE_TEXT_RATE', counter)
    monkeypatch.setattr(reliability, 'score_text', lambda t: 1.0 if t == 'good' else 0.0)

    result = reliability.filter_low_confidence(['good', 'bad'], 0.5)
    assert result == ['good']
    assert hist.values == [1.0, 0.0]
    assert counter.count == 1
