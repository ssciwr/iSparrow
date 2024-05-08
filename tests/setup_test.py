import iSparrow.sparrow_setup as sps
from pathlib import Path
import pytest
import shutil
import tempfile
from platformdirs import user_cache_dir, user_config_dir


@pytest.fixture()
def temp_dir():
    yield tempfile.mkdtemp()


@pytest.fixture()
def cleanup_after_test(temp_dir):
    yield  # This is where the test runs

    # Cleanup code goes here
    for path in [
        "test_home",
        "test_models",
        "test_output",
        "test_examples",
        "test_cache",
        "test_config",
    ]:
        print("deleting folder @", Path(temp_dir, path))
        if Path(temp_dir, path).exists():
            shutil.rmtree(Path(temp_dir, path))


@pytest.fixture()
def clean_up_test_installation():
    yield  # This is where the test runs

    # clean up stuff
    for path in [
        Path("~/iSparrow_tests").expanduser(),
        Path("~/iSparrow_tests_data").expanduser(),
        Path("~/iSparrow_tests/models").expanduser(),
        Path("~/iSparrow_tests/example").expanduser(),
        Path("~/iSparrow_tests_output").expanduser(),
        Path(user_cache_dir()) / "iSparrow_tests",
        Path(user_config_dir()) / "iSparrow_tests",
    ]:
        print("deleting folder @", path)
        if path.exists():
            shutil.rmtree(path)


@pytest.fixture()
def make_folders(temp_dir):
    for path in [
        "test_models",
        "test_examples",
        "test_cache",
    ]:
        print("making folder @", Path(temp_dir, path))
        Path(temp_dir, path).mkdir(parents=True, exist_ok=True)


def test_make_directories(temp_dir, cleanup_after_test):
    base_cfg_dirs = {
        "home": str(Path(temp_dir, "test_home")),
        "models": str(Path(temp_dir, "test_models")),
        "output": str(Path(temp_dir, "test_output")),
    }
    ish, ism, iso, ise, iscfg, iscache = sps.make_directories(base_cfg_dirs)
    print(ish, ism, iso, ise, iscfg, iscache)
    assert ish.exists()
    assert ism.exists()
    assert iso.exists()
    assert ise.exists()
    assert iscfg.exists()
    assert iscache.exists()


def test_make_directories_exceptions(cleanup_after_test):
    base_cfg_dirs = {"models": "test_models", "output": "test_output"}

    with pytest.raises(
        KeyError, match="The home folder for iSparrow must be given in the base config"
    ):
        sps.make_directories(base_cfg_dirs)

    base_cfg_dirs = {"home": "test_home", "output": "test_output"}

    with pytest.raises(
        KeyError,
        match="The models folder for iSparrow must be given in the base config",
    ):
        sps.make_directories(base_cfg_dirs)

    base_cfg_dirs = {
        "home": "test_home",
        "models": "test_models",
    }

    with pytest.raises(
        KeyError,
        match="The output folder for iSparrow must be given in the base config",
    ):
        sps.make_directories(base_cfg_dirs)


def test_download_example_data(temp_dir, make_folders, cleanup_after_test):
    example_dir = str(Path(temp_dir, "test_examples"))
    cache_dir = str(Path(temp_dir, "test_cache"))
    sps.download_example_data(example_dir, cache_dir)
    assert Path(example_dir).exists()
    assert Path(cache_dir).exists()
    assert Path(example_dir, "soundscape.wav").is_file()
    assert Path(example_dir, "corrupted.wav").is_file()
    assert Path(example_dir, "trimmed.wav").is_file()
    assert Path(example_dir, "species_list.txt").is_file()


def test_download_example_data_exceptions(make_folders, cleanup_after_test):
    example_dir = "test_examples_nonexistent"
    cache_dir = "test_cache"
    with pytest.raises(
        FileNotFoundError, match="The folder test_examples_nonexistent does not exist"
    ):
        sps.download_example_data(example_dir, cache_dir)


def test_download_model_files(temp_dir, make_folders):
    model_dir = str(Path(temp_dir, "test_models"))
    cache_dir = str(Path(temp_dir, "test_cache"))
    sps.download_model_files(model_dir, cache_dir)
    assert Path(model_dir).exists()
    assert Path(cache_dir).exists()
    assert Path(model_dir, "birdnet_default", "model.tflite").is_file()
    assert Path(model_dir, "birdnet_custom", "model.tflite").is_file()
    assert Path(model_dir, "google_perch", "saved_model.pb").is_file()


def test_download_model_files_exceptions(make_folders, cleanup_after_test):
    model_dir = "test_models_nonexistent"
    cache_dir = "test_cache"
    with pytest.raises(
        FileNotFoundError, match="The folder test_models_nonexistent does not exist"
    ):
        sps.download_model_files(model_dir, cache_dir)


def test_setup(clean_up_test_installation):
    filepath = Path(__file__).parent / "test_configs" / "install.yml"

    sps.set_up_sparrow(filepath)

    assert sps.SPARROW_HOME.exists()
    assert sps.SPARROW_EXAMPLES.exists()
    assert sps.SPARROW_MODELS.exists()
    assert sps.SPARROW_OUTPUT.exists()
    assert sps.SPARROW_CONFIG.exists()
    assert sps.SPARROW_CACHE.exists()

    assert (sps.SPARROW_MODELS / "birdnet_default" / "model.tflite").is_file()
    assert (sps.SPARROW_MODELS / "birdnet_custom" / "model.tflite").is_file()
    assert (sps.SPARROW_MODELS / "google_perch" / "saved_model.pb").is_file()
    assert (sps.SPARROW_CONFIG / "install.yml").is_file()