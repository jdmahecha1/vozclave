import logging

from vozclave import cli


def test_init_creates_config_and_refuses_to_overwrite(isolated_home, capsys):
    assert cli.main(["init"]) == 0
    config = isolated_home / "config.toml"
    assert "[[commands]]" in config.read_text(encoding="utf-8")
    assert cli.main(["init"]) == 1
    assert cli.main(["init", "--force"]) == 0


def test_third_party_info_logs_are_hidden():
    def record(name, level):
        return logging.LogRecord(name, level, __file__, 1, "msg", None, None)

    assert not cli._quiet_third_party(record("speechbrain.utils.quirks", logging.INFO))
    assert cli._quiet_third_party(record("speechbrain.utils.quirks", logging.WARNING))
    assert cli._quiet_third_party(record("vozclave", logging.INFO))


def test_run_can_write_a_log_file(tmp_path):
    log_file = tmp_path / "run.log"
    cli.setup_logging(verbose=False, log_file=str(log_file))
    logging.getLogger("vozclave").info('"okey claude" -> open (voice match 0.66)')
    logging.getLogger("speechbrain").info("noise")
    for handler in logging.root.handlers:
        handler.flush()
    text = log_file.read_text(encoding="utf-8")
    assert "voice match 0.66" in text and "noise" not in text
    logging.basicConfig(force=True)  # release the file for tmp_path cleanup


def test_missing_config_is_a_clean_error(tmp_path, capsys):
    assert cli.main(["-c", str(tmp_path / "missing.toml"), "check"]) == 1
    assert "vozclave init" in capsys.readouterr().err
