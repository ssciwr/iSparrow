from iSparrow import audio_recording as ard
from pathlib import Path
import pyaudio
from datetime import datetime
import librosa
import pytest


def test_audio_recorder_creation(folders, audio_recorder_fx):

    p = pyaudio.PyAudio()
    num_devices = p.get_device_count()
    print("checking audio devices")
    for i in range(num_devices):
        device_info = p.get_device_info_by_index(i)
        print(f"Device {i}: {device_info['name']}")

    _, DATA, _, _, _ = folders

    _, cfg = audio_recorder_fx

    assert 3 == 4
    # recorder = ard.Recorder.from_cfg(cfg["Data"]["Recording"])

    # assert recorder.output == DATA
    # assert recorder.length_in_s == 3
    # assert recorder.sample_rate == 48000
    # assert recorder.file_type == "wave"
    # assert recorder.channels == 1
    # assert recorder.num_format == pyaudio.paInt16
    # assert recorder.stream is not None
    # assert recorder.stream.is_active() is False
    # assert recorder.p is not None
    # assert recorder.mode == "record"


# def test_audio_functionality_record_mode(audio_recorder_fx):

#     _, cfg = audio_recorder_fx

#     recorder = ard.Recorder.from_cfg(cfg["Data"]["Recording"])

#     # make sure the data folder is empty before doing anything
#     for file in Path(recorder.output).iterdir():
#         file.unlink()

#     assert recorder.stream is not None
#     assert recorder.p is not None
#     assert recorder.stream.is_active() is False

#     # support for stop condition is included in recorder
#     class Condition:

#         def __init__(self):
#             self.x = 2

#         def __call__(self, _):

#             cond = self.x <= 0

#             self.x -= 1

#             return cond

#     recorder.start(stop_condition=Condition())

#     assert recorder.stream is not None

#     assert recorder.stream.is_active() is True

#     assert len(list(Path(recorder.output).iterdir())) == 2

#     current = datetime.now().strftime("%y%m%d")

#     files = list(Path(recorder.output).iterdir())

#     assert len(files) == 2

#     for audiofile in files:
#         yearmonthday = str(audiofile.name).split("_")[0]

#         assert yearmonthday == current
#         assert audiofile.suffix == ".wav"

#     # read in file to test length, samplerate, num_samples
#     with files[0] as audiofile:
#         data, rate = librosa.load(
#             Path(recorder.output) / audiofile, sr=48000, res_type="kaiser_fast"
#         )

#         duration = librosa.get_duration(y=data, sr=rate)

#         assert rate == 48000

#         # length must be sample rate (48000) times length in seconds (3)
#         assert len(data) == 48000 * 3

#         assert duration == 3

#     # try stop, restart, close functions
#     recorder.stop()

#     # use some internal variables to get handle on state
#     assert recorder.is_running is False

#     # start again
#     recorder.start(stop_condition=Condition())

#     assert recorder.is_running is True

#     files = list(Path(recorder.output).iterdir())

#     assert len(files) == 4

#     recorder._close()

#     assert len(recorder.p._streams) == 0

#     assert recorder.stream is None


# def test_audio_functionality_stream_mode(audio_recorder_fx):

#     _, cfg = audio_recorder_fx

#     cfg["Data"]["Recording"]["mode"] = "stream"

#     recorder = ard.Recorder.from_cfg(cfg["Data"]["Recording"])

#     recorder.start()

#     for _ in range(0, 3, 1):
#         length, _ = recorder.stream_audio()

#         # get back bytes array -> take into account size of individual samples
#         assert length == int(
#             recorder.sample_rate
#             * recorder.length_in_s
#             * pyaudio.get_sample_size(recorder.num_format)
#         )


# def test_audio_recorder_exceptions(audio_recorder_fx):

#     # with 'record', output folder must be given
#     with pytest.raises(ValueError) as exc_info:
#         ard.Recorder(output_folder=None, mode="record")

#     assert (
#         str(exc_info.value)
#         == "Output folder for recording object cannot be None in 'record' mode"
#     )

#     # unknown mode of operation gives exception
#     with pytest.raises(ValueError) as exc_info:
#         ard.Recorder(
#             output_folder=Path.home() / "iSparrow_data",
#             mode="some_unknown_mode_with_typos_or_something",
#         )

#     assert str(exc_info.value) == "Unknown mode. Must be 'record', 'stream'"

#     recorder = ard.Recorder(
#         output_folder=Path.home() / "iSparrow_data",
#         mode="stream",
#     )
#     with pytest.raises(RuntimeError) as exc_info:
#         recorder.stream_audio()

#     assert str(exc_info.value) == "The input stream is stopped or closed"
