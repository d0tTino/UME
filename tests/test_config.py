import pytest

from ume.config.loader import load_settings


def _set_secure_defaults(monkeypatch):
    monkeypatch.setenv("UME_AUDIT_SIGNING_KEY", "mykey")
    monkeypatch.setenv("UME_API_TOKEN", "token")
    monkeypatch.setenv("UME_OAUTH_PASSWORD", "super-secret")


def test_audit_key_default_raises_non_dev(monkeypatch):
    monkeypatch.setenv("UME_ENV", "production")
    monkeypatch.setenv("UME_AUDIT_SIGNING_KEY", "default-key")
    monkeypatch.setenv("UME_API_TOKEN", "token")
    monkeypatch.setenv("UME_OAUTH_PASSWORD", "super-secret")
    load_settings.cache_clear()
    with pytest.raises(ValueError):
        load_settings()


def test_audit_key_default_warns_in_dev(monkeypatch, caplog):
    monkeypatch.setenv("UME_ENV", "development")
    monkeypatch.setenv("UME_AUDIT_SIGNING_KEY", "default-key")
    monkeypatch.delenv("UME_API_TOKEN", raising=False)
    monkeypatch.setenv("UME_OAUTH_PASSWORD", "password")
    load_settings.cache_clear()
    with caplog.at_level("WARNING"):
        settings = load_settings()
    assert settings.UME_AUDIT_SIGNING_KEY == "default-key"
    assert "must be set to a non-default value" in caplog.text


def test_api_and_oauth_required_non_dev(monkeypatch):
    monkeypatch.setenv("UME_ENV", "production")
    monkeypatch.setenv("UME_AUDIT_SIGNING_KEY", "mykey")
    monkeypatch.delenv("UME_API_TOKEN", raising=False)
    monkeypatch.setenv("UME_OAUTH_PASSWORD", "password")
    load_settings.cache_clear()
    with pytest.raises(ValueError) as exc:
        load_settings()
    assert "UME_API_TOKEN" in str(exc.value)
    assert "UME_OAUTH_PASSWORD" in str(exc.value)


def test_secret_file_override(monkeypatch, tmp_path):
    _set_secure_defaults(monkeypatch)
    secret = tmp_path / "api_token.txt"
    secret.write_text("from-file\n", encoding="utf-8")
    monkeypatch.setenv("UME_API_TOKEN_FILE", str(secret))
    load_settings.cache_clear()
    settings = load_settings()
    assert settings.UME_API_TOKEN == "from-file"


def test_kafka_sasl_requires_credentials(monkeypatch):
    _set_secure_defaults(monkeypatch)
    monkeypatch.setenv("UME_ENV", "production")
    monkeypatch.setenv("KAFKA_SECURITY_PROTOCOL", "SASL_SSL")
    monkeypatch.delenv("KAFKA_SASL_USERNAME", raising=False)
    monkeypatch.delenv("KAFKA_SASL_PASSWORD", raising=False)
    monkeypatch.setenv("KAFKA_CA_CERT", "/tmp/ca.pem")
    load_settings.cache_clear()
    with pytest.raises(ValueError) as exc:
        load_settings()
    assert "KAFKA_SASL_USERNAME" in str(exc.value)


def test_rate_limit_default(monkeypatch):
    _set_secure_defaults(monkeypatch)
    monkeypatch.delenv("UME_RATE_LIMIT_REDIS", raising=False)
    load_settings.cache_clear()
    s = load_settings()
    assert s.UME_RATE_LIMIT_REDIS is None


def test_rate_limit_env(monkeypatch):
    _set_secure_defaults(monkeypatch)
    monkeypatch.setenv("UME_RATE_LIMIT_REDIS", "redis://localhost:6379/0")
    load_settings.cache_clear()
    s = load_settings()
    assert s.UME_RATE_LIMIT_REDIS == "redis://localhost:6379/0"
