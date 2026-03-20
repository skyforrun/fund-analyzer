import os
import pytest
from fund_analyzer.config import load_config, Settings


def test_load_config_from_file(tmp_path):
    config_file = tmp_path / "settings.yaml"
    config_file.write_text("""
database:
  host: localhost
  port: 5432
  name: test_db
  user: test_user
  password: test_pass
portfolio:
  core_ratio: 30
  satellite_ratio: 70
""")
    settings = load_config(str(config_file))
    assert settings.database.host == "localhost"
    assert settings.database.name == "test_db"
    assert settings.portfolio.core_ratio == 30
    assert settings.portfolio.satellite_ratio == 70


def test_load_config_db_password_from_env(tmp_path, monkeypatch):
    config_file = tmp_path / "settings.yaml"
    config_file.write_text("""
database:
  host: localhost
  port: 5432
  name: test_db
  user: test_user
  password: ""
""")
    monkeypatch.setenv("FUND_DB_PASSWORD", "env_secret")
    settings = load_config(str(config_file))
    assert settings.database.password == "env_secret"


def test_load_config_missing_file():
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/path.yaml")
