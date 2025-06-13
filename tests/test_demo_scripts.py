from types import SimpleNamespace


from ume import producer_demo
from ume.utils import ssl_config


def test_consumer_ssl_config(monkeypatch):
    monkeypatch.delenv("KAFKA_CA_CERT", raising=False)
    monkeypatch.delenv("KAFKA_CLIENT_CERT", raising=False)
    monkeypatch.delenv("KAFKA_CLIENT_KEY", raising=False)
    assert ssl_config() == {}

    monkeypatch.setenv("KAFKA_CA_CERT", "ca")
    monkeypatch.setenv("KAFKA_CLIENT_CERT", "cert")
    monkeypatch.setenv("KAFKA_CLIENT_KEY", "key")
    cfg = ssl_config()
    assert cfg["security.protocol"] == "SSL"
    assert cfg["ssl.ca.location"] == "ca"
    assert cfg["ssl.certificate.location"] == "cert"
    assert cfg["ssl.key.location"] == "key"


def test_producer_ssl_config(monkeypatch):
    monkeypatch.delenv("KAFKA_CA_CERT", raising=False)
    monkeypatch.delenv("KAFKA_CLIENT_CERT", raising=False)
    monkeypatch.delenv("KAFKA_CLIENT_KEY", raising=False)
    assert ssl_config() == {}

    monkeypatch.setenv("KAFKA_CA_CERT", "ca")
    monkeypatch.setenv("KAFKA_CLIENT_CERT", "cert")
    monkeypatch.setenv("KAFKA_CLIENT_KEY", "key")
    cfg = ssl_config()
    assert cfg["security.protocol"] == "SSL"
    assert cfg["ssl.ca.location"] == "ca"
    assert cfg["ssl.certificate.location"] == "cert"
    assert cfg["ssl.key.location"] == "key"


def test_delivery_report():
    msg = SimpleNamespace(topic=lambda: "t", partition=lambda: 0, offset=lambda: 1)
    producer_demo.delivery_report(None, msg)
    producer_demo.delivery_report(Exception("err"), msg)
