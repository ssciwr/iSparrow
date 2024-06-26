import pytest
from pathlib import Path
from faunanet.watcher import AnalysisEventHandler, Watcher
from faunanet.utils import wait_for_file_completion, read_yaml
import faunanet
from copy import deepcopy
import yaml
from math import isclose
import multiprocessing
import time
from datetime import datetime
import shutil


def test_watcher_construction(watch_fx, mocker):
    directories, wfx = watch_fx

    watcher = Watcher(
        wfx.data,
        wfx.output,
        wfx.models,
        "birdnet_default",
        preprocessor_config=wfx.preprocessor_cfg,
        model_config=wfx.model_cfg,
        recording_config=deepcopy(wfx.recording_cfg),
        species_predictor_config=wfx.species_predictor_cfg,
    )

    # check member variables
    assert str(watcher.input) == str(directories["data"])
    assert str(watcher.outdir) == str(directories["output"])
    assert watcher.old_output is None
    assert watcher.output is None
    assert str(watcher.model_dir) == str(directories["models"])
    assert str(watcher.model_name) == "birdnet_default"
    assert watcher.input_directory == str(directories["data"])
    assert watcher.is_running is False
    assert watcher.outdir.is_dir()
    assert watcher.model_dir.is_dir()
    assert (watcher.model_dir / watcher.model_name).is_dir()
    assert watcher.pattern == ".wav"
    assert watcher.check_time == 1
    assert watcher.delete_recordings == "never"

    default_watcher = Watcher(
        wfx.data,
        wfx.output,
        wfx.models,
        "birdnet_default",
    )

    assert str(default_watcher.input) == str(directories["data"])
    assert str(default_watcher.outdir) == str(directories["output"])
    assert str(default_watcher.model_dir) == str(directories["models"])
    assert str(default_watcher.model_name) == "birdnet_default"
    assert default_watcher.input_directory == str(directories["data"])
    assert default_watcher.is_running is False
    assert default_watcher.outdir.is_dir()
    assert default_watcher.model_dir.is_dir()
    assert (default_watcher.model_dir / default_watcher.model_name).is_dir()
    assert default_watcher.pattern == ".wav"
    assert default_watcher.check_time == 1
    assert default_watcher.delete_recordings == "never"

    watcher.output = Path(watcher.outdir) / Path(
        datetime.now().strftime("%y%m%d_%H%M%S")
    )

    watcher.output.mkdir(parents=True, exist_ok=True)

    watcher._write_config()

    with open(watcher.output / "config.yml", "r") as cfgfile:
        config = yaml.safe_load(cfgfile)

    assert config == wfx.config_should

    recording = watcher._set_up_recording(
        "birdnet_default",
        wfx.recording_cfg,
        wfx.species_predictor_cfg,
        wfx.model_cfg,
        wfx.preprocessor_cfg,
    )

    assert recording.analyzer.name == "birdnet_default"
    assert recording.path == ""
    assert recording.processor.name == "birdnet_default"
    assert recording.species_predictor.name == "birdnet_default"
    assert len(recording.allowed_species) > 0
    assert recording.species_predictor is not None
    assert isclose(recording.minimum_confidence, 0.25)
    assert isclose(recording.sensitivity, 1.0)

    # give wrong paths and check that appropriate exceptions are raised
    with pytest.raises(ValueError, match="Input directory does not exist"):
        Watcher(
            Path.home() / "faunanet_data_not_there",
            wfx.output,
            wfx.models,
            "birdnet_default",
        )

    with pytest.raises(ValueError, match="Output directory does not exist"):
        Watcher(
            wfx.data,
            Path.home() / "faunanet_output_not_there",
            wfx.models,
            "birdnet_default",
        )

    with pytest.raises(ValueError, match="Model directory does not exist"):
        Watcher(
            wfx.data,
            wfx.output,
            wfx.home / "models_not_there",
            "birdnet_default",
        )

    with pytest.raises(
        ValueError, match="Given model name does not exist in model directory"
    ):
        Watcher(
            wfx.data,
            wfx.output,
            wfx.models,
            "does_not_exist",
        )

    mocker.patch.object(
        faunanet.SpeciesPredictorBase,
        "__init__",
        raise_exception=ValueError("Simulated error occurred"),
    )
    with pytest.raises(
        ValueError,
        match="An error occured during species range predictor creation. Does you model provide a model file called 'species_presence_model'?",
    ):
        sp = Watcher(
            wfx.data,
            wfx.output,
            wfx.models,
            "birdnet_custom",
            preprocessor_config=wfx.custom_preprocessor_cfg,
            model_config=wfx.custom_model_cfg,
            recording_config=deepcopy(wfx.recording_cfg),
        )

        sp._set_up_recording(
            "birdnet_default",
            wfx.recording_cfg,
            wfx.species_predictor_cfg,
            wfx.model_cfg,
            wfx.preprocessor_cfg,
        )

    with pytest.raises(
        ValueError,
        match="'delete_recordings' must be in 'never', 'always'",
    ):
        Watcher(
            wfx.data,
            wfx.output,
            wfx.home / "models",
            "birdnet_custom",
            preprocessor_config=wfx.custom_preprocessor_cfg,
            model_config=wfx.custom_model_cfg,
            delete_recordings="some wrong value",
        )


def test_event_handler_construction(watch_fx):
    _, wfx = watch_fx

    watcher = wfx.make_watcher()

    event_handler = AnalysisEventHandler(
        watcher,
    )

    assert event_handler.pattern == ".wav"
    assert event_handler.recording.analyzer.name == "birdnet_default"
    assert event_handler.recording.processor.name == "birdnet_default"
    assert event_handler.recording.species_predictor.name == "birdnet_default"
    assert event_handler.callback == watcher.analyze


def test_watcher_lowlevel_functionality(watch_fx):
    _, wfx = watch_fx

    watcher = wfx.make_watcher()

    recording = watcher._set_up_recording(
        "birdnet_default",
        watcher.recording_config,
        watcher.species_predictor_config,
        watcher.model_config,
        watcher.preprocessor_config,
    )

    # this is normally performed by the `start` method of the watcher,
    # but because this is a low level test of the basic functionality
    # we must do it by hand here:
    watcher.output = Path(watcher.outdir) / Path(
        datetime.now().strftime("%y%m%d_%H%M%S")
    )
    watcher.output.mkdir(parents=True, exist_ok=True)

    watcher.may_do_work.set()

    # ... now we can call the functions to be tested

    watcher.analyze(wfx.home / "example" / "soundscape.wav", recording)

    assert len(list(wfx.output.iterdir())) == 1
    datafolder = list(wfx.output.iterdir())[0]

    assert len(list(datafolder.iterdir())) == 1
    assert list(datafolder.iterdir()) == [
        Path(datafolder / "results_soundscape.csv"),
    ]

    assert recording.analyzed is True
    assert recording.path == wfx.home / "example" / "soundscape.wav"
    assert len(recording.allowed_species) > 0
    assert recording.species_predictor is not None
    assert len(recording.analyzer.results) > 0


def test_watcher_daemon_lowlevel_functionality(watch_fx):
    _, wfx = watch_fx

    watcher = wfx.make_watcher()

    # this is normally performed by the `start` method of the watcher,
    # but because this is a low level test of the basic functionality
    # we must do it by hand here:
    watcher.output = Path(watcher.outdir) / Path(
        datetime.now().strftime("%y%m%d_%H%M%S")
    )
    watcher.output.mkdir(parents=True, exist_ok=True)
    # run the watcher process dry and make sure start, pause stop works
    watcher.start()
    assert watcher.may_do_work.is_set() is True
    assert watcher.is_running is True
    assert watcher.watcher_process.daemon is True
    assert watcher.watcher_process.name == "watcher_process"

    # artificially set the finish event flag because no data is there
    watcher.is_done_analyzing.set()
    watcher.pause()
    assert watcher.may_do_work.is_set() is False
    assert watcher.is_running is True
    assert watcher.is_done_analyzing.is_set() is True

    watcher.go_on()
    assert watcher.may_do_work.is_set() is True
    assert watcher.is_running is True

    # artificially set the finish flag because we have no data to work with
    watcher.is_done_analyzing.set()
    watcher.stop()
    assert watcher.is_running is False
    assert watcher.watcher_process is None
    assert watcher.may_do_work.is_set() is False
    assert watcher.is_done_analyzing.is_set() is True

    watcher.recording_cfg = wfx.recording_cfg  # necessary because it will be modified
    watcher.start()

    # artificially set finish flag because no data is there
    watcher.recording_cfg = wfx.recording_cfg  # necessary because it will be modified
    watcher.is_done_analyzing.set()
    watcher.restart()
    assert watcher.may_do_work.is_set() is True
    assert watcher.is_running is True
    assert watcher.watcher_process.daemon is True
    watcher.is_done_analyzing.set()
    watcher.stop()


def test_watcher_exceptions(watch_fx, mocker):
    _, wfx = watch_fx

    watcher = wfx.make_watcher()

    watcher.start()

    with pytest.raises(
        RuntimeError, match="watcher process still running, stop first."
    ):
        watcher.start()

    with pytest.warns(
        UserWarning, match="stop timeout expired, terminating watcher process now."
    ):
        watcher.stop()

    with pytest.raises(
        RuntimeError, match="Cannot continue watcher process, is not alive anymore."
    ):
        watcher.go_on()

    with pytest.raises(
        RuntimeError, match="Cannot stop watcher process, is not alive anymore."
    ):
        watcher.stop()

    with pytest.raises(
        RuntimeError, match="Cannot pause watcher process, is not alive anymore."
    ):
        watcher.pause()

    mocker.patch(
        "multiprocessing.Process.terminate",
        side_effect=ValueError("Simulated error occurred"),
    )

    watcher.start()

    with pytest.raises(
        RuntimeError,
        match="Something went wrong when trying to stop the watcher process",
    ):
        watcher.stop()

    watcher.watcher_process.kill()
    watcher.watcher_process = None

    mocker.patch(
        "multiprocessing.Process.start",
        side_effect=ValueError("Simulated error occurred"),
    )

    # do something to make the process start and throw
    with pytest.raises(
        RuntimeError,
        match="Something went wrong when starting the watcher process, undoing changes and returning",
    ):
        watcher.start()

    assert watcher.watcher_process is None
    assert watcher.may_do_work.is_set() is False
    assert watcher.is_running is False


def test_watcher_integrated_simple(watch_fx):
    _, wfx = watch_fx

    watcher = wfx.make_watcher()

    # make a mock recorder process that runs in the background
    number_of_files = 5

    recorder_process = multiprocessing.Process(
        target=wfx.mock_recorder,
        args=(
            wfx.home,
            wfx.data,
            number_of_files,
        ),
    )
    recorder_process.daemon = True

    # run recorder and analyzer process, record start and end times for comparison

    recorder_process.start()

    watcher.start()

    recorder_process.join()

    wfx.wait_for_event_then_do(
        condition=lambda: recorder_process.is_alive() is False,
        todo_event=lambda: recorder_process.terminate(),
        todo_else=lambda: time.sleep(0.2),
    )

    recorder_process.close()

    filename = watcher.output / f"results_example_{number_of_files-1}.csv"
    wfx.wait_for_event_then_do(
        condition=lambda: filename.is_file(),
        todo_event=lambda: watcher.stop(),
        todo_else=lambda: 1,
    )

    assert watcher.is_running is False

    assert watcher.watcher_process is None

    assert len(list(Path(wfx.data).iterdir())) == number_of_files

    results = wfx.get_folder_content(watcher.output_directory, ".csv")

    cfgs = wfx.get_folder_content(watcher.output_directory, ".yml")

    assert len(results) == number_of_files

    assert len(cfgs) == 2

    # load config and check it's consistent
    cfg = read_yaml(Path(watcher.output) / "config.yml")

    assert cfg == wfx.config_should


def test_watcher_integrated_delete_always(watch_fx):
    _, wfx = watch_fx

    watcher = wfx.make_watcher(
        delete_recordings="always",
    )

    # make a mock recorder process that runs in the background
    number_of_files = 7

    sleep_for = 10

    recorder_process = multiprocessing.Process(
        target=wfx.mock_recorder,
        args=(wfx.home, wfx.data, number_of_files, sleep_for),
    )
    watcher.start()

    wfx.wait_for_event_then_do(
        condition=lambda: watcher.is_running,
        todo_event=lambda: 1,
        todo_else=lambda: time.sleep(0.2),
    )

    recorder_process.daemon = True
    recorder_process.start()

    filename = watcher.output / "results_example_4.csv"

    # stop when the process is done analyzing file 4
    wfx.wait_for_event_then_do(
        condition=lambda: filename.is_file(),
        todo_event=lambda: watcher.stop(),
        todo_else=lambda: time.sleep(0.2),
    )

    # the following makes
    recorder_process.join()
    recorder_process.close()

    assert watcher.is_running is False
    assert watcher.watcher_process is None

    results = wfx.get_folder_content(watcher.output_directory, ".csv")

    data = wfx.get_folder_content(watcher.input_directory, ".wav")

    assert len(data) > 0
    assert number_of_files > len(results) > 0  # some data is missing


def test_watcher_integrated_delete_never(watch_fx):

    _, wfx = watch_fx

    watcher = wfx.make_watcher(
        delete_recordings="never",
    )

    # make a mock recorder process that runs in the background
    number_of_files = 7
    sleep_for = 10
    recorder_process = multiprocessing.Process(
        target=wfx.mock_recorder,
        args=(wfx.home, wfx.data, number_of_files, sleep_for),
    )
    recorder_process.daemon = True

    watcher.start()

    wfx.wait_for_event_then_do(
        condition=lambda: watcher.is_running,
        todo_event=lambda: 1,
        todo_else=lambda: time.sleep(0.2),
    )

    recorder_process.start()

    wfx.wait_for_event_then_do(
        condition=lambda: (watcher.output / "results_example_4.csv").is_file()
        and wait_for_file_completion(watcher.output / "results_example_4.csv"),
        todo_event=lambda: watcher.stop(),
        todo_else=lambda: 1,
    )

    recorder_process.join()

    recorder_process.close()

    assert watcher.is_running is False
    assert watcher.watcher_process is None

    wfx.delete_in_output(watcher, ["results_example_6.csv", "results_example_5.csv"])

    data = wfx.get_folder_content(watcher.input_directory, ".wav")

    results = wfx.get_folder_content(watcher.output_directory, ".csv")

    assert len(data) == number_of_files

    assert len(results) == number_of_files - 2


def test_change_analyzer(watch_fx):
    directories, wfx = watch_fx

    watcher = wfx.make_watcher(
        delete_recordings="never",
    )

    number_of_files = 15

    sleep_for = 3

    recorder_process = multiprocessing.Process(
        target=wfx.mock_recorder,
        args=(wfx.home, wfx.data, number_of_files, sleep_for),
    )
    recorder_process.daemon = True
    watcher.start()

    wfx.wait_for_event_then_do(
        condition=lambda: watcher.is_running,
        todo_event=lambda: 1,
        todo_else=lambda: time.sleep(0.2),
    )

    recorder_process.start()

    filename = watcher.output / "results_example_4.csv"

    wfx.wait_for_event_then_do(
        condition=lambda: filename.is_file(),
        todo_event=lambda: watcher.change_analyzer(
            "birdnet_custom",
            preprocessor_config=wfx.custom_preprocessor_cfg,
            model_config=wfx.custom_model_cfg,
            recording_config=wfx.changed_custom_recording_cfg,
            delete_recordings="always",
        ),
        todo_else=lambda: time.sleep(0.3),
    )

    # the following makes
    recorder_process.join()

    recorder_process.close()
    assert (watcher.old_output / Path(watcher.batchfile_name)).is_file() is True
    assert watcher.model_name == "birdnet_custom"
    assert watcher.output_directory != watcher.old_output
    assert (watcher.output / Path("config.yml")).is_file() is True
    assert watcher.preprocessor_config == wfx.custom_preprocessor_cfg
    assert watcher.model_config == wfx.custom_model_cfg
    assert watcher.recording_config == wfx.changed_custom_recording_cfg
    assert watcher.is_running is True
    assert watcher.watcher_process is not None
    assert watcher.input_directory == str(directories["data"])
    assert watcher.output.is_dir() is True  # not yet created
    assert (watcher.model_dir / watcher.model_name).is_dir()
    assert watcher.pattern == ".wav"
    assert watcher.check_time == 1
    assert watcher.delete_recordings == "always"
    # wait for the final file to be completed
    filename = watcher.output / f"results_example_{number_of_files-1}.csv"

    wfx.wait_for_event_then_do(
        condition=lambda: filename.is_file(),
        todo_event=lambda: watcher.stop(),
        todo_else=lambda: time.sleep(0.3),
    )

    current_files = [f for f in watcher.output.iterdir() if f.suffix == ".csv"]
    old_files = [f for f in watcher.old_output.iterdir() if f.suffix == ".csv"]

    assert len(current_files) > 0  # some analyzed files must be in the new directory
    assert len(old_files) > 0
    assert 0 < len(list(Path(wfx.data).iterdir())) < number_of_files
    assert number_of_files >= len(old_files) + len(current_files)  # some data can be


def test_change_analyzer_recovery(watch_fx, mocker):

    _, wfx = watch_fx

    watcher = wfx.make_watcher(
        delete_recordings="never",
    )

    number_of_files = 15

    sleep_for = 6

    recorder_process = multiprocessing.Process(
        target=wfx.mock_recorder,
        args=(wfx.home, wfx.data, number_of_files, sleep_for),
    )

    recorder_process.daemon = True

    watcher.start()

    wfx.wait_for_event_then_do(
        condition=lambda: watcher.is_running,
        todo_event=lambda: 1,
        todo_else=lambda: time.sleep(0.5),
    )

    recorder_process.start()

    assert watcher.is_running
    assert watcher.watcher_process is not None

    filename = watcher.output / "results_example_4.csv"

    wfx.wait_for_event_then_do(
        condition=lambda: filename.is_file(),
        todo_event=lambda: 1,
        todo_else=lambda: time.sleep(0.3),
    )

    # patch the start method so we get a mock exception that is propagated through the system
    mocker.patch(
        "faunanet.Watcher.restart",
        side_effect=ValueError("Simulated error occurred"),
    )
    try:
        watcher.change_analyzer(
            "birdnet_custom",
            preprocessor_config=wfx.custom_preprocessor_cfg,
            model_config=wfx.custom_model_cfg,
            recording_config=wfx.changed_custom_recording_cfg,
            delete_recordings="always",
        )
    except RuntimeError as e:
        e == RuntimeError(
            "Error when while trying to change the watcher process, any changes made have been undone. The process needs to be restarted manually. This operation may have led to data loss."
        )
        watcher.start()

    assert watcher.is_running
    assert watcher.model_name == "birdnet_default"
    assert watcher.delete_recordings == "never"

    filename = watcher.output / f"results_example_{number_of_files -1}.csv"
    wfx.wait_for_event_then_do(
        condition=lambda: filename.is_file() and wait_for_file_completion(filename),
        todo_event=lambda: watcher.stop(),
        todo_else=lambda: time.sleep(1),
    )

    results_folders = [f for f in watcher.outdir.iterdir() if f.is_dir()]
    results = [f for f in watcher.output.iterdir() if f.suffix == ".csv"]
    old_results = [f for f in watcher.old_output.iterdir() if f.suffix == ".csv"]

    assert watcher.old_output != watcher.output
    assert len(results_folders) == 2
    assert len(old_results) == 5
    assert len(results) <= number_of_files - 1

    old_cfg = read_yaml(watcher.old_output / "config.yml")
    new_cfg = read_yaml(watcher.output / "config.yml")
    assert old_cfg["Analysis"]["Model"] == new_cfg["Analysis"]["Model"]
    assert old_cfg["Analysis"]["Preprocessor"] == new_cfg["Analysis"]["Preprocessor"]
    assert old_cfg["Analysis"]["Recording"] == new_cfg["Analysis"]["Recording"]
    recorder_process.join()
    recorder_process.close()

    mocker.patch(
        "faunanet.Watcher.clean_up",
        side_effect=ValueError("Simulated error occurred"),
    )
    try:
        watcher.change_analyzer(
            "birdnet_custom",
            preprocessor_config=wfx.custom_preprocessor_cfg,
            model_config=wfx.custom_model_cfg,
            recording_config=wfx.changed_custom_recording_cfg,
            delete_recordings="always",
        )
    except RuntimeError as e:
        e == RuntimeError(
            "Error when cleaning up data after analyzer change, watcher is running. This error may have lead to corrupt data in newly created analysis files."
        )
        watcher.start()

    assert watcher.is_running
    assert watcher.model_name == "birdnet_default"
    assert watcher.delete_recordings == "never"


def test_change_analyzer_exception(watch_fx, mocker):
    # patch the start method so we get a mock exception that is propagated through the system
    _, wfx = watch_fx

    watcher = wfx.make_watcher(
        delete_recordings="never",
    )

    old_recording_cfg = deepcopy(watcher.recording_config)
    old_model_cfg = deepcopy(watcher.model_config)
    old_preprocessor_cfg = deepcopy(watcher.preprocessor_config)
    old_species_predictor_cfg = deepcopy(watcher.species_predictor_config)

    number_of_files = 14

    sleep_for = 3

    recorder_process = multiprocessing.Process(
        target=wfx.mock_recorder,
        args=(wfx.home, wfx.data, number_of_files, sleep_for),
    )

    recorder_process.daemon = True

    watcher.start()

    wfx.wait_for_event_then_do(
        condition=lambda: watcher.is_running,
        todo_event=lambda: 1,
        todo_else=lambda: time.sleep(0.25),
    )

    recorder_process.start()

    assert watcher.is_running
    assert watcher.watcher_process is not None

    filename = watcher.output / f"results_example_{4}.csv"
    wfx.wait_for_event_then_do(
        condition=lambda: filename.is_file(),
        todo_event=lambda: 1,  # do nothing, just stop waiting,
        todo_else=lambda: time.sleep(0.2),
    )

    old_output = watcher.output_directory

    with pytest.raises(
        ValueError, match="Given model name does not exist in model dir."
    ):
        watcher.change_analyzer(
            "nonexistent_model",
            preprocessor_config=wfx.custom_preprocessor_cfg,
            model_config=wfx.custom_model_cfg,
            recording_config=wfx.changed_custom_recording_cfg,
            delete_recordings="always",
        )
    assert watcher.model_name == "birdnet_default"
    assert watcher.is_running
    assert watcher.output_directory == old_output
    assert watcher.model_config == old_model_cfg
    assert watcher.preprocessor_config == old_preprocessor_cfg
    assert watcher.recording_config == old_recording_cfg
    assert watcher.species_predictor_config == old_species_predictor_cfg

    mocker.patch(
        "faunanet.Watcher.clean_up",
        side_effect=ValueError("Simulated error occurred"),
    )

    with pytest.raises(
        RuntimeError,
        match="Error when while trying to change the watcher process, any changes made have been undone. The process needs to be restarted manually. This operation may have led to data loss.",
    ):
        watcher.change_analyzer(
            "birdnet_custom",
            preprocessor_config=wfx.custom_preprocessor_cfg,
            model_config=wfx.custom_model_cfg,
            recording_config=wfx.changed_custom_recording_cfg,
            delete_recordings="always",
        )

    assert watcher.is_running is False
    recorder_process.join()
    recorder_process.close()


def test_cleanup_simple(
    watch_fx,
):
    _, wfx = watch_fx

    watcher = wfx.make_watcher(delete_recordings="always")

    number_of_files = 25

    sleep_for = 5

    assert len(wfx.get_folder_content(watcher.input_directory, watcher.pattern)) == 0

    recorder_process = multiprocessing.Process(
        target=wfx.mock_recorder,
        args=(wfx.home, wfx.data, number_of_files, sleep_for),
    )

    recorder_process.daemon = True

    watcher.start()

    assert len(wfx.get_folder_content(watcher.output_directory, ".csv")) <= 0
    old_output = watcher.output

    wfx.wait_for_event_then_do(
        condition=lambda: watcher.is_running,
        todo_event=lambda: recorder_process.start(),
        todo_else=lambda: time.sleep(0.25),
    )

    filename = watcher.output / "results_example_5.csv"

    wfx.wait_for_event_then_do(
        condition=lambda: filename.is_file(),
        todo_event=lambda: watcher.pause(),
        todo_else=lambda: time.sleep(0.2),
    )

    assert len([f for f in old_output.iterdir() if f.suffix == ".csv"]) <= 7

    filename = watcher.input / f"example_{9}.wav"

    wfx.wait_for_event_then_do(
        condition=lambda: filename.is_file(),
        todo_event=lambda: watcher.go_on(),
        todo_else=lambda: time.sleep(0.2),
    )

    watcher.change_analyzer(
        "birdnet_custom",
        preprocessor_config=wfx.custom_preprocessor_cfg,
        model_config=wfx.custom_model_cfg,
        recording_config=wfx.changed_custom_recording_cfg,
        delete_recordings="never",
    )

    for i in range(0, 10):
        assert (watcher.input / f"example_{i}.wav").is_file() is False
        assert (watcher.old_output / f"results_example_{i}.csv").is_file() is True

    assert set([f.name for f in old_output.iterdir() if f.suffix == ".yml"]) == set(
        [
            watcher.batchfile_name,
            "config.yml",
        ]
    )

    assert [f.name for f in old_output.iterdir() if f.suffix == ".txt"] == [
        "missings.txt",
    ]

    # because we copy over the same file over and over as a mock recording,
    # we can compare with old files to make sure the clean-up method behaves
    # like the normal analysis function
    missing_files = wfx.read_missings(old_output)

    assert len(missing_files) > 0

    reference = wfx.read_csv(old_output / "results_example_0.csv")

    for m in missing_files:
        rows = wfx.read_csv(old_output / f"results_{Path(m).stem}.csv")
        assert rows == reference

    filename = watcher.input / f"example_{16}.wav"
    wfx.wait_for_event_then_do(
        condition=lambda: filename.is_file(),
        todo_event=lambda: watcher.stop(),
        todo_else=lambda: time.sleep(0.2),
    )

    recorder_process.join()

    recorder_process.close()

    old_files = [f.stem for f in watcher.old_output.iterdir() if f.suffix == ".csv"]

    pre_cleanup_files = [f.stem for f in watcher.output.iterdir() if f.suffix == ".csv"]

    assert len(pre_cleanup_files) <= 8

    assert set([f.name for f in watcher.output.iterdir() if f.suffix == ".yml"]) == set(
        [
            watcher.batchfile_name,
            "config.yml",
        ]
    )

    for i in range(len(old_files), len(old_files) + len(pre_cleanup_files)):
        assert Path(watcher.input / f"example_{i}.wav").is_file() is True

    watcher.clean_up()

    assert [f.name for f in watcher.output.iterdir() if f.suffix == ".txt"] == [
        "missings.txt",
    ]

    missing_files = wfx.read_missings(old_output)

    assert len(missing_files) > 0
    post_cleanup_files = [
        f.stem for f in watcher.output.iterdir() if f.suffix == ".csv"
    ]

    all_files = [f"results_example_{i}" for i in range(0, number_of_files)]
    assert set(old_files + post_cleanup_files) == set(all_files)


def test_cleanup_many_folders(watch_fx):
    # this tests the cleanup method across multiple input and output folders
    number_of_files = 20
    sleep_for = 3
    stop_inds = [6, 12]
    outputfolders = []

    _, wfx = watch_fx
    watcher = wfx.make_watcher(delete_recordings="always")

    old_input = watcher.input

    # function to create multiple folders of input data and puts the results into multiple output folders in which data is missing
    def create_dummy_output(watcher: Watcher, input: Path):
        recorder_process = multiprocessing.Process(
            target=wfx.mock_recorder,
            args=(wfx.home, input, number_of_files, sleep_for),
        )

        recorder_process.daemon = True
        watcher.input = input
        watcher.start()
        outputfolders.append(watcher.output)

        wfx.wait_for_event_then_do(
            condition=lambda: watcher.is_running,
            todo_event=lambda: recorder_process.start(),
            todo_else=lambda: time.sleep(0.25),
        )

        for i in range(0, len(stop_inds)):
            wfx.wait_for_event_then_do(
                condition=lambda idx=i: (
                    watcher.input / f"example_{stop_inds[idx]}.wav"
                ).is_file()
                and wait_for_file_completion(
                    watcher.input / f"example_{stop_inds[idx]}.wav"
                ),
                todo_event=lambda: watcher.stop(),
                todo_else=lambda: time.sleep(0.2),
            )
            time.sleep(6)
            watcher.start()
            outputfolders.append(watcher.output)

        wfx.wait_for_event_then_do(
            condition=lambda idx=i: (
                watcher.input / f"example_{number_of_files - 3}.wav"
            ).is_file()
            and wait_for_file_completion(
                watcher.input / f"example_{number_of_files - 3}.wav"
            ),
            todo_event=lambda: watcher.stop(),
            todo_else=lambda: time.sleep(0.2),
        )

        wfx.wait_for_event_then_do(
            condition=lambda: watcher.is_running is False,
            todo_event=lambda: None,
            todo_else=lambda: time.sleep(0.2),
        )

        recorder_process.join()
        recorder_process.close()

    create_dummy_output(watcher, old_input)

    new_input = Path(watcher.input.parent, f"test_{2}")
    new_input.mkdir(exist_ok=True, parents=True)

    create_dummy_output(watcher, new_input)

    assert watcher.is_running is False

    num_wav_files = sum(
        1
        for inputdir in [old_input, new_input]
        for f in inputdir.iterdir()
        if f.is_file() and f.suffix == ".wav"
    )
    num_csv_files = sum(
        1
        for out in outputfolders
        for f in out.iterdir()
        if f.is_file() and f.suffix == ".csv"
    )

    expected_missings = num_wav_files

    assert 0 < num_wav_files < 2 * number_of_files
    assert 0 < num_csv_files < 2 * number_of_files

    for out in outputfolders:
        assert out / watcher.batchfile_name in out.iterdir()
        assert out / "config.yml" in out.iterdir()

    watcher.clean_up()
    num_wav_files = sum(
        1
        for inputdir in [old_input, new_input]
        for f in inputdir.iterdir()
        if f.is_file() and f.suffix == ".wav"
    )
    num_csv_files = sum(
        1
        for out in outputfolders
        for f in out.iterdir()
        if f.is_file() and f.suffix == ".csv"
    )

    assert num_wav_files == 0
    assert num_csv_files == 2 * number_of_files

    actual_missings = 0
    for out in outputfolders:
        assert out / "missings.txt" in list(out.iterdir())

        with open(out / "missings.txt", "r") as f:
            missings = f.readlines()
        assert len(missings) > 0
        actual_missings += len(missings)

    assert expected_missings == actual_missings

    shutil.rmtree(new_input)


def test_cleanup_exceptions(watch_fx, mocker):
    _, wfx = watch_fx

    watcher = wfx.make_watcher()

    with pytest.raises(
        RuntimeError,
        match="No output folders found to clean up",
    ):
        watcher.clean_up()

    number_of_files = 8

    sleep_for = 3

    recorder_process = multiprocessing.Process(
        target=wfx.mock_recorder,
        args=(wfx.home, wfx.data, number_of_files, sleep_for),
    )

    recorder_process.daemon = True

    watcher.start()

    wfx.wait_for_event_then_do(
        condition=lambda: watcher.is_running,
        todo_event=lambda: recorder_process.start(),
        todo_else=lambda: time.sleep(0.25),
    )

    with pytest.warns(
        UserWarning,
        match="Cannot clean up current output directory while watcher is running",
    ):
        watcher.clean_up()

    recorder_process.join()
    recorder_process.close()

    watcher.stop()
