import pytest
from pathlib import Path
import iSparrow.repl as repl
import iSparrow.sparrow_setup as sps
import shutil

INSTALL_FILE = "install.yml"


@pytest.fixture()
def clean_up_test_installation():
    yield

    cfg = sps.utils.read_yaml(
        Path(__file__).parent / "test_install_config" / INSTALL_FILE
    )
    for _, path in cfg["Directories"].items():
        if Path(path).expanduser().exists():
            shutil.rmtree(Path(path).expanduser(), ignore_errors=True)

    if (Path(sps.user_config_dir()) / "iSparrow_tests").exists():
        shutil.rmtree(
            Path(sps.user_config_dir()) / "iSparrow_tests", ignore_errors=True
        )

    if (Path(sps.user_cache_dir()) / "iSparrow_tests").exists():
        shutil.rmtree(Path(sps.user_cache_dir()) / "iSparrow_tests", ignore_errors=True)


def test_do_set_up(clean_up_test_installation, patch_functions):
    tmpdir = patch_functions

    filepath = Path(__file__).parent / "test_install_config" / INSTALL_FILE
    cfg = sps.utils.read_yaml(filepath)["Directories"]

    assert Path(cfg["home"].replace("~", str(tmpdir))).exists() is False
    assert Path(cfg["models"].replace("~", str(tmpdir))).exists() is False
    assert Path(cfg["output"].replace("~", str(tmpdir))).exists() is False

    sparrow_cmd = repl.SparrowCmd()
    sparrow_cmd.do_set_up("--cfg=" + str(filepath))

    tflite_file = "model.tflite"

    assert Path(cfg["home"].replace("~", str(tmpdir))).exists() is True
    assert Path(cfg["models"].replace("~", str(tmpdir))).exists() is True
    assert Path(cfg["output"].replace("~", str(tmpdir))).exists() is True

    assert (
        Path(cfg["models"].replace("~", str(tmpdir))) / "birdnet_default" / tflite_file
    ).is_file()
    assert (
        Path(cfg["models"].replace("~", str(tmpdir))) / "birdnet_custom" / tflite_file
    ).is_file()
    assert (
        Path(cfg["models"].replace("~", str(tmpdir)))
        / "google_perch"
        / "saved_model.pb"
    ).is_file()


@pytest.mark.parametrize(
    "input, expected",
    [
        (
            "--cfg./tests/test_configs",
            "Could not set up iSparrow Invalid input. Expected options structure is --name=<arg> caused by:  None\n",
        ),
        (
            "--cfg=./tests/test_configs --stuff=superfluous",
            "Expected 1 blocks of the form --name=<arg> with names ['--cfg']\n",
        ),
        ("", "No config file provided, falling back to default"),
    ],
)
def test_do_set_up_failure(input, expected, mocker, capsys, patch_functions):
    capsys.readouterr()

    sparrow_cmd = repl.SparrowCmd()
    sparrow_cmd.do_set_up(input)
    out, _ = capsys.readouterr()
    assert expected in out
    capsys.readouterr()


def test_do_set_up_setup_exception(mocker, capsys, clean_up_test_installation):
    mocker.patch(
        "iSparrow.sparrow_setup.set_up_sparrow", side_effect=Exception("RuntimeError")
    )
    sparrow_cmd = repl.SparrowCmd()
    sparrow_cmd.do_set_up("--cfg=./tests/test_configs")
    out, _ = capsys.readouterr()
    assert "Could not set up iSparrow RuntimeError caused by:  None\n" in out
    capsys.readouterr()


def test_do_get_setup_info(patch_functions, capsys, clean_up_test_installation):

    filepath = Path(__file__).parent / "test_install_config" / INSTALL_FILE
    cfg = sps.utils.read_yaml(filepath)

    sparrow_cmd = repl.SparrowCmd()
    sparrow_cmd.do_set_up("--cfg=" + str(filepath))

    dummy_path = Path(sps.user_config_dir()) / "iSparrow"
    dummy_path.mkdir(parents=True, exist_ok=True)

    shutil.copy(filepath, dummy_path / INSTALL_FILE)

    capsys.readouterr()
    sparrow_cmd.do_get_setup_info("")
    out, _ = capsys.readouterr()
    assert (
        "config directories:  "
        + str(
            [
                Path(sps.user_config_dir()) / "iSparrow",
            ]
        )
        in out
    )
    assert (
        "cache directories:  "
        + str(
            [
                Path(sps.user_cache_dir()) / "iSparrow",
            ]
        )
        in out
    )
    assert "Current setup: " in out
    for key in cfg["Directories"]:
        assert key in out

    shutil.rmtree(dummy_path)


def test_do_get_setup_info_failure(patch_functions, capsys):

    sparrow_cmd = repl.SparrowCmd()
    Path(sps.user_config_dir(), "iSparrow").mkdir(parents=True, exist_ok=True)
    Path(sps.user_cache_dir(), "iSparrow").mkdir(parents=True, exist_ok=True)

    sparrow_cmd.do_get_setup_info("input not allowed")
    out, _ = capsys.readouterr()
    assert "Invalid input. Expected no arguments." in out

    # no setup, hence no installation info
    capsys.readouterr()
    sparrow_cmd.do_get_setup_info("")
    out, _ = capsys.readouterr()

    assert (
        "config directories:  " + str([Path(sps.user_config_dir()) / "iSparrow"]) in out
    )
    assert (
        "cache directories:  "
        + str(
            [
                Path(sps.user_cache_dir()) / "iSparrow",
            ]
        )
        in out
    )
    assert "No further setup information found" in out

    shutil.rmtree(Path(sps.user_config_dir()))
    shutil.rmtree(Path(sps.user_cache_dir()))
