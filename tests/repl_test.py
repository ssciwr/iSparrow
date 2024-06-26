import pytest
from pathlib import Path
from importlib.resources import files
import shutil
import faunanet
import faunanet.repl as repl
import time
from copy import deepcopy
from queue import Queue

CFG_PATH = "--cfg=./tests/test_configs/watcher_custom.yml"


@pytest.fixture()
def make_mock_install(patch_functions):
    tmpdir = patch_functions

    packagebase = files(faunanet)
    cfg = repl.read_yaml(packagebase / "install.yml")["Directories"]

    for name, path in cfg.items():
        Path(path).mkdir(parents=True, exist_ok=True)

    Path(tmpdir, "faunanet_tests_data").mkdir(parents=True, exist_ok=True)
    Path(tmpdir, "faunanet_tests_output").mkdir(parents=True, exist_ok=True)

    iscfg = Path(repl.user_config_dir()) / "faunanet"
    iscache = Path(repl.user_cache_dir()) / "faunanet"

    iscfg.mkdir(parents=True, exist_ok=True)
    iscache.mkdir(parents=True, exist_ok=True)

    ism = Path(cfg["models"])
    ise = Path(cfg["home"]) / "example"
    ism.mkdir(parents=True, exist_ok=True)
    ise.mkdir(parents=True, exist_ok=True)

    faunanet.faunanet_setup.download_model_files(ism)
    faunanet.faunanet_setup.download_example_data(ise)

    shutil.copy(Path(packagebase, "install.yml"), iscfg)
    shutil.copy(Path(packagebase, "default.yml"), iscfg)

    yield tmpdir

    shutil.rmtree(ise)
    for name, path in cfg.items():
        if Path(path).exists():
            shutil.rmtree(Path(path).expanduser())
    shutil.rmtree(Path(tmpdir, "faunanet_tests_data"))
    shutil.rmtree(Path(tmpdir, "faunanet_tests_output"))
    shutil.rmtree(tmpdir)


def wait_for_watcher_status(faunanet_cmd, status=lambda w: w.is_running):
    i = 0
    while True:
        if i > 10:
            assert False
        if status(faunanet_cmd.watcher):
            break
        else:
            time.sleep(3)
            i += 1


def test_dispatch_on_watcher(mocker, capsys):
    faunanet_cmd = repl.FaunanetCmd()
    faunanet_cmd.watcher = None

    capsys.readouterr()

    def do_is_none_func(s):
        print("Watcher is None")

    def do_is_sleeping_func(s):
        print("Watcher is sleeping")

    def do_is_running_func(s):
        print("Watcher is running")

    def do_else_func(s):
        print("Watcher is in an unknown state")

    def do_failure_func(s, e):
        print("Watcher has failed")

    faunanet_cmd.dispatch_on_watcher(
        do_is_none=do_is_none_func,
        do_is_sleeping=do_is_sleeping_func,
        do_is_running=do_is_running_func,
        do_else=do_else_func,
        do_failure=do_failure_func,
    )

    out, _ = capsys.readouterr()
    assert "Watcher is None" in out

    faunanet_cmd.watcher = mocker.patch("faunanet.repl.Watcher", autospec=True)

    type(faunanet_cmd.watcher).is_running = mocker.PropertyMock(return_value=True)
    type(faunanet_cmd.watcher).is_sleeping = mocker.PropertyMock(return_value=False)

    capsys.readouterr()
    faunanet_cmd.dispatch_on_watcher(
        do_is_none=do_is_none_func,
        do_is_sleeping=do_is_sleeping_func,
        do_is_running=do_is_running_func,
        do_else=do_else_func,
        do_failure=do_failure_func,
    )
    out, _ = capsys.readouterr()
    assert "Watcher is running" in out

    type(faunanet_cmd.watcher).is_sleeping = mocker.PropertyMock(return_value=True)
    type(faunanet_cmd.watcher).is_running = mocker.PropertyMock(return_value=False)

    capsys.readouterr()
    faunanet_cmd.dispatch_on_watcher(
        do_is_none=do_is_none_func,
        do_is_sleeping=do_is_sleeping_func,
        do_is_running=do_is_running_func,
        do_else=do_else_func,
        do_failure=do_failure_func,
    )
    out, _ = capsys.readouterr()

    assert "Watcher is sleeping" in out

    type(faunanet_cmd.watcher).is_sleeping = mocker.PropertyMock(return_value=False)
    type(faunanet_cmd.watcher).is_running = mocker.PropertyMock(return_value=False)

    capsys.readouterr()
    faunanet_cmd.dispatch_on_watcher(
        do_is_none=do_is_none_func,
        do_is_sleeping=do_is_sleeping_func,
        do_is_running=do_is_running_func,
        do_else=do_else_func,
        do_failure=do_failure_func,
    )
    out, _ = capsys.readouterr()

    assert "Watcher is in an unknown state" in out

    def raise_exception(s):
        raise RuntimeError("RuntimeError")

    type(faunanet_cmd.watcher).is_sleeping = mocker.PropertyMock(return_value=False)

    type(faunanet_cmd.watcher).is_running = mocker.PropertyMock(return_value=True)

    capsys.readouterr()
    faunanet_cmd.dispatch_on_watcher(
        do_is_none=do_is_none_func,
        do_is_sleeping=do_is_sleeping_func,
        do_is_running=raise_exception,
        do_else=do_else_func,
        do_failure=do_failure_func,
    )
    out, _ = capsys.readouterr()

    assert "Watcher has failed" in out


def test_process_line_into_kwargs():
    assert repl.process_line_into_kwargs(
        "--cfg=./tests/test_configs --stuff=other", keywords=["cfg", "stuff"]
    ) == {"cfg": "./tests/test_configs", "stuff": "other"}

    with pytest.raises(
        ValueError, match="Invalid input. Expected options structure is --name=<arg>"
    ):
        repl.process_line_into_kwargs(
            "./tests/test_configs",
            keywords=[
                "cfg",
            ],
        )

    with pytest.raises(ValueError, match="Keywords must be provided with passed line"):
        repl.process_line_into_kwargs("--cfg=./tests/test_configs")

    assert repl.process_line_into_kwargs("") == {}


@pytest.mark.parametrize(
    "input, keywords, message",
    [
        (
            "-no equality sign",
            [
                "cfg",
            ],
            "Invalid input. Expected options structure is --name=<arg>",
        ),
        (
            "--cfg=./tests/test_configs",
            [],
            "Keywords must be provided with passed line",
        ),
        (
            "--cfg=./tests/test_configs",
            None,
            "Keywords must be provided with passed line",
        ),
        (
            "--cfg=./tests/test_configs",
            [
                "rkg",
            ],
            "Keyword rkg not found in passed line",
        ),
    ],
)
def test_process_line_into_kwargs_failures(input, keywords, message):
    with pytest.raises(ValueError, match=message):
        repl.process_line_into_kwargs(input, keywords=keywords)


def test_do_start_custom(make_mock_install, capsys):
    tmpdir = make_mock_install

    faunanet_cmd = repl.FaunanetCmd()
    faunanet_cmd.do_start(CFG_PATH)
    wait_for_watcher_status(faunanet_cmd)

    assert faunanet_cmd.watcher is not None
    assert faunanet_cmd.watcher.outdir == tmpdir / "faunanet_tests_output"
    assert faunanet_cmd.watcher.input_directory == str(tmpdir / "faunanet_tests_data")
    assert faunanet_cmd.watcher.model_dir == tmpdir / "faunanet/models"
    assert faunanet_cmd.watcher.is_running is True
    assert faunanet_cmd.watcher.delete_recordings == "always"
    assert faunanet_cmd.watcher.pattern == ".mp3"
    faunanet_cmd.watcher.stop()
    assert faunanet_cmd.watcher.is_running is False

    capsys.readouterr()
    faunanet_cmd.do_start(CFG_PATH)

    out, _ = capsys.readouterr()
    assert faunanet_cmd.watcher.is_running is True
    assert (
        "It appears that there is a watcher process that is not running. Trying to start with current parameters. Use  the 'change_analyzer' command to change the parameters.\nstart the watcher process\n"
        in out
    )

    capsys.readouterr()
    faunanet_cmd.do_start("")
    out, _ = capsys.readouterr()
    assert (
        "The watcher is running. Cannot be started again with different parameters. Try 'change_analyzer' to use different parameters.\n"
        in out
    )

    faunanet_cmd.watcher.stop()
    assert faunanet_cmd.watcher.is_running is False


@pytest.mark.parametrize(
    "input, expected, status",
    [
        (
            "--cfg./tests/test_configs/watcher_custom.yml",
            "Something in the start command parsing went wrong. Check your passed commands. Caused by:  Invalid input. Expected options structure is --name=<arg>\n",
            True,
        ),
        (
            CFG_PATH + " --stuff=superfluous",
            "Invalid input. Expected 1 blocks of the form --name=<arg> with names ['--cfg']\n",
            True,
        ),
        ("", "No config file provided, falling back to default", False),
    ],
)
def test_do_start_failure(input, expected, status, make_mock_install, capsys):
    capsys.readouterr()
    faunanet_cmd = repl.FaunanetCmd()
    faunanet_cmd.do_start(input)
    out, _ = capsys.readouterr()
    assert expected in out
    assert (faunanet_cmd.watcher is None) is status

    if faunanet_cmd.watcher is not None and faunanet_cmd.watcher.is_running is True:
        faunanet_cmd.watcher.stop()


def test_do_start_exception_in_watcher_start(make_mock_install, mocker, capsys):
    mocker.patch.object(
        faunanet.Watcher, "start", side_effect=Exception("RuntimeError")
    )
    faunanet_cmd = repl.FaunanetCmd()

    capsys.readouterr()
    faunanet_cmd.do_start(CFG_PATH)
    out, _ = capsys.readouterr()
    assert (
        "Something went wrong while trying to start the watcher: RuntimeError caused by  None. A new start attempt can be made when the error has been addressed.\n"
        in out
    )

    if faunanet_cmd.watcher is not None and faunanet_cmd.watcher.is_running is True:
        faunanet_cmd.watcher.stop()


def test_do_start_exception_in_watcher_build(make_mock_install, mocker, capsys):
    mocker.patch.object(
        faunanet.Watcher, "__init__", side_effect=Exception("RuntimeError")
    )
    faunanet_cmd = repl.FaunanetCmd()
    capsys.readouterr()
    faunanet_cmd.do_start(CFG_PATH)
    out, _ = capsys.readouterr()
    assert (
        "An error occured while trying to build the watcher: RuntimeError caused by None\n"
        in out
    )
    if faunanet_cmd.watcher is not None and faunanet_cmd.watcher.is_running is True:
        faunanet_cmd.watcher.stop()


def test_do_stop(make_mock_install):
    faunanet_cmd = repl.FaunanetCmd()
    faunanet_cmd.do_start(CFG_PATH)
    wait_for_watcher_status(faunanet_cmd)
    assert faunanet_cmd.watcher.is_running is True
    faunanet_cmd.do_stop("")
    time.sleep(30)
    assert faunanet_cmd.watcher.is_running is False


def test_do_stop_failure(make_mock_install, capsys):
    faunanet_cmd = repl.FaunanetCmd()

    faunanet_cmd.do_start(CFG_PATH)
    wait_for_watcher_status(faunanet_cmd)

    capsys.readouterr()
    faunanet_cmd.do_stop("something_wrong")
    out, _ = capsys.readouterr()
    assert "Invalid input. Expected no arguments." in out

    faunanet_cmd.do_start(CFG_PATH)
    wait_for_watcher_status(faunanet_cmd)

    assert faunanet_cmd.watcher.is_running is True
    faunanet_cmd.watcher.stop()
    capsys.readouterr()
    faunanet_cmd.do_stop("")
    out, _ = capsys.readouterr()
    assert "Cannot stop watcher, is not running\n" in out


def test_do_stop_exceptions(make_mock_install, capsys, mocker):
    mocker.patch("faunanet.Watcher.stop", side_effect=Exception("RuntimeError"))

    faunanet_cmd = repl.FaunanetCmd()

    faunanet_cmd.do_start(CFG_PATH)

    wait_for_watcher_status(faunanet_cmd)

    capsys.readouterr()

    faunanet_cmd.do_stop("")

    out, _ = capsys.readouterr()
    assert (
        "Could not stop watcher: RuntimeError caused by None. Watcher process will be killed now and all resources released. This may have left data in a corrupt state. A new watcher must be started if this session is to be continued.\n"
        in out
    )

    if faunanet_cmd.watcher is not None and faunanet_cmd.watcher.is_running is True:
        faunanet_cmd.watcher.stop()


def test_do_exit(capsys):
    faunanet_cmd = repl.FaunanetCmd()

    capsys.readouterr()
    faunanet_cmd.do_exit("wrong args")
    out, _ = capsys.readouterr()
    assert "Invalid input. Expected no arguments.\n" in out

    capsys.readouterr()

    value = faunanet_cmd.do_exit("")

    assert value is True

    out, _ = capsys.readouterr()

    assert "Exiting faunanet shell\n" in out


def test_do_pause(make_mock_install):
    faunanet_cmd = repl.FaunanetCmd()
    faunanet_cmd.do_start(CFG_PATH)
    wait_for_watcher_status(faunanet_cmd)

    assert faunanet_cmd.watcher.is_running is True
    # fake work done
    faunanet_cmd.watcher.is_done_analyzing.set()
    faunanet_cmd.do_pause("")
    assert faunanet_cmd.watcher.is_sleeping is True
    assert faunanet_cmd.watcher.is_running is True
    faunanet_cmd.watcher.go_on()
    faunanet_cmd.watcher.stop()
    assert faunanet_cmd.watcher.is_running is False


def test_do_pause_failures(make_mock_install, capsys):
    faunanet_cmd = repl.FaunanetCmd()
    faunanet_cmd.do_start(CFG_PATH)
    assert faunanet_cmd.watcher.is_running is True
    time.sleep(5)
    faunanet_cmd.watcher.is_done_analyzing.set()
    faunanet_cmd.do_pause("cfg=wrong_argument")
    out, _ = capsys.readouterr()
    assert "Invalid input. Expected no arguments.\n" in out

    faunanet_cmd.watcher.stop()
    i = 0
    while True:
        if i > 10:
            assert False
        if faunanet_cmd.watcher.is_running is False:
            break
        else:
            time.sleep(3)
            i += 1
    capsys.readouterr()
    faunanet_cmd.watcher.is_done_analyzing.set()
    faunanet_cmd.do_pause("")
    out, _ = capsys.readouterr()
    assert "Cannot pause watcher, is not running\n" in out

    capsys.readouterr()
    faunanet_cmd.watcher = None
    faunanet_cmd.do_pause("")
    out, _ = capsys.readouterr()
    assert "Cannot pause watcher, no watcher present\n" in out

    faunanet_cmd.do_start(CFG_PATH)

    wait_for_watcher_status(faunanet_cmd)

    faunanet_cmd.watcher.is_done_analyzing.set()
    faunanet_cmd.watcher.pause()

    capsys.readouterr()
    faunanet_cmd.do_pause("")
    out, _ = capsys.readouterr()
    assert "Cannot pause watcher, is already sleeping\n" in out


def test_do_pause_exception(make_mock_install, capsys, mocker):
    faunanet_cmd = repl.FaunanetCmd()
    faunanet_cmd.do_start(CFG_PATH)
    assert faunanet_cmd.watcher.is_running is True
    wait_for_watcher_status(faunanet_cmd)

    mocker.patch("faunanet.Watcher.pause", side_effect=Exception("RuntimeError"))
    faunanet_cmd.watcher.is_done_analyzing.set()
    capsys.readouterr()
    faunanet_cmd.do_pause("")
    out, _ = capsys.readouterr()
    assert "Could not pause watcher: RuntimeError caused by None\n" in out
    assert faunanet_cmd.watcher is not None
    assert faunanet_cmd.watcher.is_running is True

    faunanet_cmd.watcher.stop()
    assert faunanet_cmd.watcher.is_running is False


def test_do_continue(make_mock_install):

    faunanet_cmd = repl.FaunanetCmd()
    faunanet_cmd.do_start(CFG_PATH)
    assert faunanet_cmd.watcher.is_running is True
    wait_for_watcher_status(faunanet_cmd)

    # fake work done
    faunanet_cmd.watcher.is_done_analyzing.set()
    faunanet_cmd.do_pause("")
    assert faunanet_cmd.watcher.is_sleeping is True
    assert faunanet_cmd.watcher.is_running is True
    faunanet_cmd.do_continue("")
    assert faunanet_cmd.watcher.is_sleeping is False
    assert faunanet_cmd.watcher.is_running is True
    faunanet_cmd.watcher.stop()
    assert faunanet_cmd.watcher.is_running is False


def test_do_continue_failure(make_mock_install, capsys):

    faunanet_cmd = repl.FaunanetCmd()
    faunanet_cmd.do_start(CFG_PATH)
    wait_for_watcher_status(faunanet_cmd)
    assert faunanet_cmd.watcher.is_running is True
    faunanet_cmd.watcher.is_done_analyzing.set()
    faunanet_cmd.do_pause("")
    assert faunanet_cmd.watcher.is_sleeping is True
    assert faunanet_cmd.watcher.is_running is True

    capsys.readouterr()
    faunanet_cmd.do_continue("cfg=wrong_argument")
    out, _ = capsys.readouterr()
    assert "Invalid input. Expected no arguments.\n" in out

    faunanet_cmd.do_stop("")
    wait_for_watcher_status(faunanet_cmd, status=lambda w: w.is_running is False)
    faunanet_cmd.watcher = None

    capsys.readouterr()
    assert faunanet_cmd.watcher is None

    faunanet_cmd.do_continue("")

    out, _ = capsys.readouterr()
    assert "Cannot continue watcher, no watcher present\n" in out

    faunanet_cmd.do_start(CFG_PATH)

    wait_for_watcher_status(faunanet_cmd)

    capsys.readouterr()
    faunanet_cmd.do_continue("")
    out, _ = capsys.readouterr()

    assert "Cannot continue watcher, is not sleeping\n" in out

    faunanet_cmd.watcher.stop()

    capsys.readouterr()
    faunanet_cmd.do_continue("")
    out, _ = capsys.readouterr()

    assert "Cannot continue watcher, is not running\n" in out


def test_do_continue_exception(make_mock_install, capsys, mocker):

    mocker.patch("faunanet.Watcher.go_on", side_effect=Exception("RuntimeError"))

    faunanet_cmd = repl.FaunanetCmd()
    faunanet_cmd.do_start(CFG_PATH)
    wait_for_watcher_status(faunanet_cmd)

    assert faunanet_cmd.watcher.is_running is True

    faunanet_cmd.watcher.is_done_analyzing.set()
    faunanet_cmd.do_pause("")
    assert faunanet_cmd.watcher.is_sleeping is True
    assert faunanet_cmd.watcher.is_running is True

    capsys.readouterr()
    faunanet_cmd.do_continue("")
    out, _ = capsys.readouterr()
    assert "Could not continue watcher: RuntimeError caused by None\n" in out


def test_do_restart(make_mock_install):
    faunanet_cmd = repl.FaunanetCmd()
    faunanet_cmd.do_start(CFG_PATH)
    wait_for_watcher_status(faunanet_cmd)
    assert faunanet_cmd.watcher.is_running is True
    assert faunanet_cmd.watcher.is_sleeping is False
    old_output = deepcopy(faunanet_cmd.watcher.output)
    faunanet_cmd.do_restart("")
    wait_for_watcher_status(faunanet_cmd)
    assert faunanet_cmd.watcher.is_running is True
    assert faunanet_cmd.watcher.is_sleeping is False
    assert old_output != faunanet_cmd.watcher.output
    faunanet_cmd.watcher.stop()
    wait_for_watcher_status(faunanet_cmd, status=lambda w: w.is_running is False)
    assert faunanet_cmd.watcher.is_running is False


def test_do_restart_failure(make_mock_install, capsys):
    faunanet_cmd = repl.FaunanetCmd()

    faunanet_cmd.do_start(CFG_PATH)

    wait_for_watcher_status(faunanet_cmd)

    assert faunanet_cmd.watcher.is_running is True
    assert faunanet_cmd.watcher.is_sleeping is False

    capsys.readouterr()
    faunanet_cmd.do_restart("wrong input")
    out, _ = capsys.readouterr()
    assert "Invalid input. Expected no arguments.\n" in out

    faunanet_cmd.watcher.is_done_analyzing.set()
    faunanet_cmd.watcher.pause()
    wait_for_watcher_status(faunanet_cmd, status=lambda w: w.is_sleeping is True)

    capsys.readouterr()
    faunanet_cmd.do_restart("")
    out, _ = capsys.readouterr()
    assert "Cannot restart watcher, is sleeping and must be continued first\n" in out

    faunanet_cmd.watcher.stop()
    wait_for_watcher_status(faunanet_cmd, status=lambda w: w.is_running is False)

    capsys.readouterr()
    faunanet_cmd.do_restart("")
    out, _ = capsys.readouterr()
    assert "Cannot restart watcher, is not running\n" in out


def test_do_restart_exceptions(make_mock_install, capsys, mocker):
    mocker.patch.object(faunanet.Watcher, "stop", side_effect=Exception("RuntimeError"))
    faunanet_cmd = repl.FaunanetCmd()

    faunanet_cmd.do_start(CFG_PATH)

    wait_for_watcher_status(faunanet_cmd)

    assert faunanet_cmd.watcher.is_running is True
    assert faunanet_cmd.watcher.is_sleeping is False

    capsys.readouterr()
    faunanet_cmd.do_restart("")
    out, _ = capsys.readouterr()
    assert (
        "trying to restart the watcher process\nCould not restart watcher: RuntimeError caused by None\n"
        in out
    )


def test_do_change_analyzer(make_mock_install):
    faunanet_cmd = repl.FaunanetCmd()
    faunanet_cmd.do_start("")

    wait_for_watcher_status(faunanet_cmd)

    assert faunanet_cmd.watcher.is_running is True
    assert faunanet_cmd.watcher.is_sleeping is False

    old_out = deepcopy(faunanet_cmd.watcher.output)
    faunanet_cmd.do_change_analyzer(CFG_PATH)
    wait_for_watcher_status(faunanet_cmd)

    assert faunanet_cmd.watcher.is_running is True
    assert faunanet_cmd.watcher.is_sleeping is False
    assert faunanet_cmd.watcher.delete_recordings == "always"
    assert faunanet_cmd.watcher.pattern == ".mp3"
    assert old_out != faunanet_cmd.watcher.output
    faunanet_cmd.watcher.is_done_analyzing.set()
    faunanet_cmd.watcher.may_do_work.clear()

    faunanet_cmd.watcher.stop()
    wait_for_watcher_status(faunanet_cmd, status=lambda w: w.is_running is False)
    assert faunanet_cmd.watcher.is_running is False


def test_change_analyzer_exception(make_mock_install, capsys, mocker):
    mocker.patch.object(
        faunanet.Watcher,
        "change_analyzer",
        side_effect=Exception("RuntimeError"),
    )

    faunanet_cmd = repl.FaunanetCmd()

    capsys.readouterr()
    faunanet_cmd.do_change_analyzer("")
    out, _ = capsys.readouterr()
    assert "No watcher present, cannot change analyzer\n" in out

    faunanet_cmd.do_start(CFG_PATH)

    wait_for_watcher_status(faunanet_cmd)

    faunanet_cmd.watcher.is_done_analyzing.set()

    capsys.readouterr()
    faunanet_cmd.do_change_analyzer(CFG_PATH)

    out, _ = capsys.readouterr()

    assert (
        "An error occured when changing analyzer: RuntimeError, caused by None\n" in out
    )

    if faunanet_cmd.watcher is not None and faunanet_cmd.watcher.is_running is True:
        faunanet_cmd.watcher.stop()


def test_change_analyzer_failure(make_mock_install, capsys):
    faunanet_cmd = repl.FaunanetCmd()
    capsys.readouterr()
    faunanet_cmd.do_change_analyzer("")
    out, _ = capsys.readouterr()
    assert "No watcher present, cannot change analyzer\n" in out

    faunanet_cmd.do_start(CFG_PATH)

    wait_for_watcher_status(faunanet_cmd)

    faunanet_cmd.watcher.is_done_analyzing.set()
    faunanet_cmd.watcher.pause()
    wait_for_watcher_status(faunanet_cmd, status=lambda w: w.is_sleeping is True)

    capsys.readouterr()
    faunanet_cmd.do_change_analyzer(CFG_PATH)
    out, _ = capsys.readouterr()
    assert "Cannot change analyzer, watcher is sleeping\n" in out

    faunanet_cmd.watcher.go_on()

    wait_for_watcher_status(faunanet_cmd, status=lambda w: w.is_sleeping is False)

    capsys.readouterr()
    faunanet_cmd.do_change_analyzer(CFG_PATH + " --other=superfluous")
    out, _ = capsys.readouterr()
    assert (
        "Invalid input. Expected 1 blocks of the form --name=<arg> with names ['--cfg']\n"
        in out
    )

    faunanet_cmd.watcher.stop()
    wait_for_watcher_status(faunanet_cmd, status=lambda w: w.is_running is False)
    capsys.readouterr()
    faunanet_cmd.do_change_analyzer(CFG_PATH)
    out, _ = capsys.readouterr()
    assert "Cannot change analyzer, watcher is not running\n" in out

    faunanet_cmd.watcher = None
    capsys.readouterr()
    faunanet_cmd.do_change_analyzer(CFG_PATH)
    out, _ = capsys.readouterr()
    assert "No watcher present, cannot change analyzer\n" in out


def test_do_status(make_mock_install, capsys):
    faunanet_cmd = repl.FaunanetCmd()
    faunanet_cmd.do_start(CFG_PATH)
    assert faunanet_cmd.watcher.is_running is True
    assert faunanet_cmd.watcher.is_sleeping is False

    wait_for_watcher_status(faunanet_cmd)

    capsys.readouterr()
    faunanet_cmd.do_status("")
    out, _ = capsys.readouterr()
    assert "is running: True\nis sleeping: False\nmay do work: True\n" in out
    assert faunanet_cmd.watcher.is_running is True
    assert faunanet_cmd.watcher.is_sleeping is False
    faunanet_cmd.watcher.stop()
    assert faunanet_cmd.watcher.is_running is False

    capsys.readouterr()
    faunanet_cmd.do_status("wrong input")
    out, _ = capsys.readouterr()
    assert "Invalid input. Expected no arguments.\n" in out

    faunanet_cmd.watcher = None

    capsys.readouterr()
    faunanet_cmd.do_status("")
    out, _ = capsys.readouterr()
    assert "No watcher present, cannot check status\n" in out


def test_do_cleanup_no_watcher(mocker, capsys):
    faunanet_cmd = repl.FaunanetCmd()

    faunanet_cmd.do_cleanup("")
    captured = capsys.readouterr()
    assert "Cannot run cleanup, no watcher present" in captured.out


def test_do_cleanup_with_arguments(mocker, capsys):
    faunanet_cmd = repl.FaunanetCmd()
    faunanet_cmd.watcher = mocker.Mock()
    faunanet_cmd.do_cleanup("some arguments")
    captured = capsys.readouterr()
    assert "Invalid input. Expected no arguments." in captured.out


def test_do_cleanup_watcher_sleeping(mocker):
    faunanet_cmd = repl.FaunanetCmd()
    faunanet_cmd.watcher = mocker.Mock()
    mocker.patch.object(faunanet_cmd.watcher, "is_sleeping", return_value=True)
    mocker.patch.object(faunanet_cmd.watcher, "is_running", return_value=False)
    faunanet_cmd.do_cleanup("")
    faunanet_cmd.watcher.clean_up.assert_called_once()


def test_do_cleanup_watcher_failure(mocker, capsys, make_mock_install):
    faunanet_cmd = repl.FaunanetCmd()
    faunanet_cmd.watcher = mocker.Mock()
    mocker.patch.object(
        faunanet_cmd.watcher, "clean_up", side_effect=Exception("RuntimeError")
    )

    capsys.readouterr()
    faunanet_cmd.do_cleanup("")
    captured = capsys.readouterr()
    assert "Error while running cleanup: " in captured.out

    faunanet_cmd.watcher.stop()


def test_cmdloop_keyboard_interrupt(mocker, capsys):
    faunanet_cmd = repl.FaunanetCmd()
    assert faunanet_cmd.running
    mocker.patch.object(repl.cmd.Cmd, "cmdloop", side_effect=KeyboardInterrupt)
    capsys.readouterr()
    faunanet_cmd.cmdloop()
    out, _ = capsys.readouterr()
    assert not faunanet_cmd.running
    assert "Execution Interrupted\n" in out
    assert "Exiting shell...\n" in out


def test_cmdloop_exception(mocker, capsys):
    faunanet_cmd = repl.FaunanetCmd()
    assert faunanet_cmd.running

    def except_set_false():
        faunanet_cmd.running = False
        raise RuntimeError("dummy exception")

    mocker.patch.object(repl.cmd.Cmd, "cmdloop", side_effect=except_set_false)
    capsys.readouterr()
    faunanet_cmd.cmdloop()
    out, _ = capsys.readouterr()
    assert "An error occured:  dummy exception  caused by:  None\n" in out
    assert (
        "If you tried to modify the watcher, make sure to restart it or exit and start a new session"
        in out
    )


def test_cmdloop_exception_queue(mocker, capsys):
    faunanet_cmd = repl.FaunanetCmd()

    def set_false():
        faunanet_cmd.running = False

    mocker.patch.object(repl.cmd.Cmd, "cmdloop", side_effect=set_false)

    watcher_mock = mocker.Mock()
    watcher_mock.exception_queue = Queue()
    faunanet_cmd.watcher = watcher_mock

    faunanet_cmd.watcher.exception_queue.put((Exception("Test"), "Traceback"))

    # Now, you can assign this mock to the watcher member of the FaunanetCmd instance
    faunanet_cmd.watcher = watcher_mock

    faunanet_cmd.running = True
    capsys.readouterr()
    faunanet_cmd.cmdloop()
    out, _ = capsys.readouterr()
    assert "An error occurred in the watcher subprocess: " in out
    assert "Traceback: " in out
