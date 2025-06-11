from ume.query import Neo4jQueryEngine


class DummySession:
    def __init__(self):
        self.last = None

    def run(self, query, parameters=None):
        self.last = (query, parameters)

        class R:
            def __init__(self):
                self._data = {"ok": True}

            def data(self):
                return self._data

        return [R()]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass


class DummyDriver:
    def __init__(self):
        self.session_obj = DummySession()

    def session(self):
        return self.session_obj

    def close(self):
        pass


def test_execute_cypher_returns_records():
    engine = Neo4jQueryEngine(DummyDriver())
    result = engine.execute_cypher("MATCH (n) RETURN n")
    assert result == [{"ok": True}]
    assert engine._driver.session_obj.last == ("MATCH (n) RETURN n", {})
