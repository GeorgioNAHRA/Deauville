import pytest

from deauville.cli import main


def test_cli_commands(capsys):
    main([])
    assert "Deauville Festival du Rire 2027" in capsys.readouterr().out
    main(["programme", "2027-06-11"])
    assert "After Hours" in capsys.readouterr().out
    main(["artists"])
    assert "Nora Lebrun: 4 show(s)" in capsys.readouterr().out
    main(["now", "--at", "2027-06-12T01:00"])
    output = capsys.readouterr().out
    assert "After Hours" in output
    assert "Up next:" in output


def test_cli_clear_file_error(tmp_path, capsys):
    with pytest.raises(SystemExit) as error:
        main(["--data", str(tmp_path / "missing.json")])
    assert error.value.code == 1
    output = capsys.readouterr().err
    assert "Cannot read festival data" in output
    assert "Traceback" not in output


def test_cli_invalid_day(capsys):
    with pytest.raises(SystemExit):
        main(["programme", "June 11"])
    assert "YYYY-MM-DD" in capsys.readouterr().err
