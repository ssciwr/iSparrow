from iSparrow import utils
from pathlib import Path
import yaml
import pytest
import pandas as pd


@pytest.fixture
def audio_recorder_fx():
    filepath = Path(__file__).resolve()
    testpath = filepath.parent.parent
    with open(testpath / Path("test_configs") / "cfg_default.yml", "r") as file:
        default_cfg = yaml.safe_load(file)

    return testpath, default_cfg
