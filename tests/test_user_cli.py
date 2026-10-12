"""The quixote command line: every subcommand's help, usage errors exit 64."""
import pytest

from quixote.cli import EXIT_USAGE, main

SUBCOMMANDS = ["example", "run", "audit", "power", "split", "grade"]


@pytest.mark.parametrize("cmd", SUBCOMMANDS)
def test_help_exits_zero(cmd, capsys):
    with pytest.raises(SystemExit) as e:
        main([cmd, "--help"])
    assert e.value.code == 0 and "usage" in capsys.readouterr().out


def test_top_level_help(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    out = capsys.readouterr().out
    assert e.value.code == 0 and all(c in out for c in SUBCOMMANDS + ["sancho"])


def test_sancho_help():
    try:
        code = main(["sancho", "--help"])
    except SystemExit as e:
        code = e.code
    assert code in (0, EXIT_USAGE)


@pytest.mark.parametrize("argv", [[], ["nope"], ["run"], ["audit"], ["power", "--years", "10"],
                                  ["power", "--years", "x", "--size", "3"],
                                  ["power", "--years", "10", "--size", "3", "--class", "c.json"]])
def test_usage_errors_exit_64(argv):
    with pytest.raises(SystemExit) as e:
        main(argv)
    assert e.value.code == EXIT_USAGE


def test_input_errors_exit_64(tmp_path, capsys):
    assert main(["audit", str(tmp_path / "missing.json"), "--panel", "p.npz", "--class", "c.json"]) == EXIT_USAGE
    assert main(["power", "--years", "10", "--size", "0"]) == EXIT_USAGE
    assert "refused" in capsys.readouterr().err


def test_power_by_size(capsys):
    assert main(["power", "--years", "10", "--size", "128"]) == 0
    assert "the bar" in capsys.readouterr().out


def test_power_by_class_needs_panel_for_all(tmp_path):
    c = tmp_path / "c.json"
    c.write_text('{"kind": "subsets", "features": "all", "max_size": 2}')
    assert main(["power", "--years", "10", "--class", str(c)]) == EXIT_USAGE
