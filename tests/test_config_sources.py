from __future__ import annotations

from daylib.config import Settings


def test_settings_ignore_repo_root_dotenv(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text(
        "AWS_PROFILE=from-dotenv\nAWS_DEFAULT_REGION=eu-central-1\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)

    settings = Settings()

    assert settings.aws_profile is None
    assert settings.aws_default_region == "us-west-2"
