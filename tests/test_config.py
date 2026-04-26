import os
from pathlib import Path

from scout.config import _load_dotenv


def test_dotenv_loads_keys(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("SCOUT_TEST_ALPHA", raising=False)
    monkeypatch.delenv("SCOUT_TEST_BETA", raising=False)
    f = tmp_path / ".env"
    f.write_text("SCOUT_TEST_ALPHA=hello\n# a comment\n\nSCOUT_TEST_BETA='multi word'\n")
    _load_dotenv(f)
    assert os.environ["SCOUT_TEST_ALPHA"] == "hello"
    assert os.environ["SCOUT_TEST_BETA"] == "multi word"


def test_dotenv_does_not_override_existing(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SCOUT_TEST_GAMMA", "from_shell")
    (tmp_path / ".env").write_text("SCOUT_TEST_GAMMA=from_file\n")
    _load_dotenv(tmp_path / ".env")
    assert os.environ["SCOUT_TEST_GAMMA"] == "from_shell"


def test_dotenv_missing_file_is_silent(tmp_path: Path):
    _load_dotenv(tmp_path / "no_such_file")  # must not raise
