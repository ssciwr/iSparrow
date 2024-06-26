import faunanet.faunanet_setup as sps
from pathlib import Path
import pytest
import shutil
import tempfile

tflite_file = "model.tflite"


@pytest.fixture()
def temp_dir():
    tmp = tempfile.mkdtemp()
    yield tmp
    shutil.rmtree(tmp)


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
        if Path(temp_dir, path).exists():
            shutil.rmtree(Path(temp_dir, path))


@pytest.fixture()
def make_folders(temp_dir):
    for path in [
        "test_models",
        "test_examples",
        "test_cache",
    ]:
        Path(temp_dir, path).mkdir(parents=True, exist_ok=True)

    yield


@pytest.fixture()
def clean_up_test_installation():
    yield

    cfg = sps.utils.read_yaml(
        Path(__file__).parent / "test_install_config" / "install.yml"
    )
    for _, path in cfg["Directories"].items():
        if Path(path).expanduser().exists():
            shutil.rmtree(Path(path).expanduser(), ignore_errors=True)

    if (Path(sps.user_config_dir()) / "faunanet_tests").exists():
        shutil.rmtree(
            Path(sps.user_config_dir()) / "faunanet_tests", ignore_errors=True
        )

    if (Path(sps.user_cache_dir()) / "faunanet_tests").exists():
        shutil.rmtree(Path(sps.user_cache_dir()) / "faunanet_tests", ignore_errors=True)


def test_make_directories(temp_dir, cleanup_after_test):
    base_cfg_dirs = {
        "home": str(Path(temp_dir, "test_home")),
        "models": str(Path(temp_dir, "test_models")),
        "output": str(Path(temp_dir, "test_output")),
    }
    ish, ism, iso, ise, iscfg, iscache = sps.make_directories(base_cfg_dirs)

    assert ish.exists()
    assert ism.exists()
    assert iso.exists()
    assert ise.exists()
    assert iscfg.exists()
    assert iscache.exists()


def test_make_directories_exceptions(cleanup_after_test, patch_functions):
    base_cfg_dirs = {"models": "test_models", "output": "test_output"}

    with pytest.raises(
        KeyError, match="The home folder for faunanet must be given in the base config"
    ):
        sps.make_directories(base_cfg_dirs)

    base_cfg_dirs = {"home": "test_home", "output": "test_output"}

    with pytest.raises(
        KeyError,
        match="The models folder for faunanet must be given in the base config",
    ):
        sps.make_directories(base_cfg_dirs)

    base_cfg_dirs = {
        "home": "test_home",
        "models": "test_models",
    }

    with pytest.raises(
        KeyError,
        match="The output folder for faunanet must be given in the base config",
    ):
        sps.make_directories(base_cfg_dirs)


def test_download_example_data(
    temp_dir, make_folders, cleanup_after_test, patch_functions
):
    example_dir = str(Path(temp_dir, "test_examples"))

    sps.download_example_data(example_dir)

    assert Path(example_dir).exists()
    assert Path(example_dir, "soundscape.wav").is_file()
    assert Path(example_dir, "corrupted.wav").is_file()
    assert Path(example_dir, "trimmed.wav").is_file()
    assert Path(example_dir, "species_list.txt").is_file()


def test_download_example_data_exceptions(
    make_folders, cleanup_after_test, patch_functions
):
    example_dir = "test_examples_nonexistent"
    with pytest.raises(
        FileNotFoundError, match="The folder test_examples_nonexistent does not exist"
    ):
        sps.download_example_data(example_dir)


def test_download_model_files(temp_dir, make_folders, patch_functions):
    model_dir = str(Path(temp_dir, "test_models"))
    sps.download_model_files(model_dir)
    assert Path(model_dir).exists()
    assert Path(model_dir, "birdnet_default", tflite_file).is_file()
    assert Path(model_dir, "birdnet_custom", tflite_file).is_file()
    assert Path(model_dir, "google_perch", "saved_model.pb").is_file()


def test_download_model_files_exceptions(
    make_folders, cleanup_after_test, patch_functions
):
    model_dir = "test_models_nonexistent"
    with pytest.raises(
        FileNotFoundError, match="The folder test_models_nonexistent does not exist"
    ):
        sps.download_model_files(model_dir)


def test_setup(clean_up_test_installation, patch_functions):
    filepath = Path(__file__).parent / "test_install_config" / "install.yml"

    sps.set_up(filepath)

    assert sps.FAUNANET_HOME.exists()
    assert sps.FAUNANET_EXAMPLES.exists()
    assert sps.FAUNANET_MODELS.exists()
    assert sps.FAUNANET_OUTPUT.exists()
    assert sps.FAUNANET_CONFIG.exists()
    assert sps.FAUNANET_CACHE.exists()

    assert (sps.FAUNANET_MODELS / "birdnet_default" / tflite_file).is_file()
    assert (sps.FAUNANET_MODELS / "birdnet_custom" / tflite_file).is_file()
    assert (sps.FAUNANET_MODELS / "google_perch" / "saved_model.pb").is_file()
    assert (sps.FAUNANET_CONFIG / "install.yml").is_file()

    assert (sps.FAUNANET_HOME / "docker" / "docker-compose.yml").is_file()
    assert (sps.FAUNANET_HOME / "docker" / "faunanet.dockerfile").is_file()
