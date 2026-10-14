from vozclave import cli


def test_init_creates_config_and_refuses_to_overwrite(isolated_home, capsys):
    assert cli.main(["init"]) == 0
    config = isolated_home / "config.toml"
    assert "[[commands]]" in config.read_text(encoding="utf-8")
    assert cli.main(["init"]) == 1
    assert cli.main(["init", "--force"]) == 0


def test_missing_config_is_a_clean_error(tmp_path, capsys):
    assert cli.main(["-c", str(tmp_path / "missing.toml"), "check"]) == 1
    assert "vozclave init" in capsys.readouterr().err
