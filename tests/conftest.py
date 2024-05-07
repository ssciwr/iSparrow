import multiprocessing

multiprocessing.set_start_method("spawn", True)
import pytest
import shutil
import multiprocessing
from pathlib import Path
import os
import iSparrow.sparrow_setup as sps
from iSparrow.utils import read_yaml

from .fixtures.recording_fixtures import recording_fx
from .fixtures.preprocessor_fixtures import preprocessor_fx, preprocessor_fx_google
from .fixtures.model_fixtures import model_fx
from .fixtures.watcher_fixtures import watch_fx

# set test mode
os.environ["SPARROW_TEST_MODE"] = "True"

HOME = ""
DATA = ""
OUTPUT = ""
CONFIG = ""
CACHE = ""


@pytest.fixture(scope="function", autouse=True)
def install(request):
    print("Creating iSparrow folders and downloading data... ")
    sps.set_up_sparrow(Path(__file__).parent / Path("test_configs"))
    print("Installation finished")

    global HOME, DATA, OUTPUT, CONFIG, CACHE
    HOME = sps.SPARROW_HOME
    DATA = sps.SPARROW_DATA
    OUTPUT = sps.SPARROW_OUTPUT
    CONFIG = sps.SPARROW_CONFIG
    CACHE = sps.SPARROW_CACHE

    # remove again after usage
    def teardown():
        shutil.rmtree(str(DATA))
        shutil.rmtree(str(OUTPUT))
        shutil.rmtree(str(HOME))
        shutil.rmtree(str(CONFIG))
        shutil.rmtree(str(CACHE))

    request.addfinalizer(teardown)
