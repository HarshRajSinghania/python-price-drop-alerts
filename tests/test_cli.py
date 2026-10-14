from price_alerts import cli


def test_config_error_exits_1(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "watchlist.yaml").write_text("settings: {}\nitems: []\n")
    assert cli.main(["--dry-run"]) == 1


def test_missing_token_exits_1(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no .env here
    monkeypatch.delenv("MAILTRAP_API_TOKEN", raising=False)
    monkeypatch.delenv("DRY_RUN", raising=False)
    (tmp_path / "watchlist.yaml").write_text(
        "settings:\n  from_email: a@example.com\n  default_recipients: [b@example.com]\n"
        "items:\n  - name: X\n    url: https://example.com/x\n"
    )
    assert cli.main([]) == 1
