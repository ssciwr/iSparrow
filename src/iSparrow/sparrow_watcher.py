from iSparrow import SparrowRecording
from iSparrow import SpeciesPredictorBase
import iSparrow.utils as utils

from pathlib import Path
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from time import sleep
from datetime import datetime
from copy import deepcopy
import yaml
import multiprocessing
import warnings
import csv
from copy import deepcopy


class AnalysisEventHandler(FileSystemEventHandler):
    """
    AnalysisEventHandler Custom event handler that calls a function whenever
    the a new file with a matching extension is created in the watched directory and that waits for a
    multiprocessing.Event object to be true.

    Base:
        FileSystemEventHandler: watchdog.FilesystemEventHandler

    Methods:
    --------
    on_created(event): Run the callback whenever a newly created file with a matching pattern is found.
    """

    def __init__(
        self,
        watcher,
    ):
        """
        __init__ Create a new AnalysisEventHandler object.

        Args:
            callback (callable): Callback functionw hen
            pattern (str, optional): file apttern. Defaults to ".wav".
            watcher: (SparrowWatcher): Watcher this Handler is used with
        """
        self.pattern = watcher.pattern
        self.recording = watcher._set_up_recording(watcher.model_name, watcher.config)
        self.callback = watcher.analyze

    def on_created(self, event):
        """
        on_created Call the callback function of the caller object whenever a new file is created
                    that has the desired file extension. Waits on the stored multiprocessing.event and only
                    runs if its flag is true.

        Args:
            event (threading.Event): Event triggering the analysis, i.e., a new audio file appears and is ready to be processessed in the watched folder
        """
        if (
            Path(event.src_path).is_file()
            and Path(event.src_path).suffix == self.pattern
        ):
            self.callback(event.src_path, self.recording)


def watchertask(watcher):
    """
    watchertask Function to run in the watcher process.
    Checks if there is a new file every 'watcher.check_time' seconds and
    analyze the file with a sound classifier model.

    Args:
        watcher (SparrowWatcher): Watcher class to run this task with

    Raises:
        RuntimeError: When something goes wrong inside the analyzer process.
    """

    # build the recorder
    observer = Observer()

    event_handler = AnalysisEventHandler(
        watcher,
    )
    observer.schedule(event_handler, watcher.input, recursive=True)
    observer.start()

    try:
        while True:
            sleep(watcher.check_time)
    except KeyboardInterrupt:
        observer.stop()
    except Exception as e:
        observer.stop()
        raise RuntimeError(
            "Something went wrong in the watcher/analysis process"
        ) from e

    observer.join()


class SparrowWatcher:
    """
    Class that watches a directory and applies a classifier model to each new file that is created in it.
    Supports model exchange on the fly.
    To this end, it creates a daemon thread in which the classifier runs,
    such that commands can be processed in the main process.

    Methods:
    --------
    change_analyzer: Exchange the classifier model with one that is present in the model dir.
    analyze: Analyze a file and write the results to the output directory.
    save_results: Save the results to the output directory as a csv file.
    stop: Pause the watcher thread.
    go_on: Continue the watcher thread
    check_analysis: Go over the input and output directory and repeat analysis for
                    all files for which there is not corresponding file in the output
                    directory.

    """

    def _write_config(
        self,
    ):
        """
        _write_config Write out the set of parameters a Watcher instance has been created with.

        """
        config = {
            "Analysis": {
                "input": str(self.input),
                "output": str(self.output),
                "delete_recording": self.delete_recordings,
                "pattern": self.pattern,
                "check_time": self.check_time,
                "model_dir": str(self.model_dir),
                "Preprocessor": deepcopy(self.preprocessor_config),
                "Model": deepcopy(self.model_config),
                "Recording": deepcopy(self.recording_config),
                "SpeciesPredictor": deepcopy(self.species_predictor_config),
            }
        }

        config["Analysis"]["Model"]["name"] = self.model_name

        try:
            with open(self.output / "config.yml", "w") as ymlfile:
                yaml.safe_dump(config, ymlfile)
        except Exception as e:
            raise RuntimeError("Error during config writing ", e) from e

    def _set_up_recording(self, model_name: str, config: dict) -> SparrowRecording:
        """
        set_up_recording Set up the recording object used for analyzing audio files.

        Raises:
            ValueError: In case the species presence predictor is used. When the an error occurs during the creation of the species predictor model.

        Returns:
            SparrowRecording: New instance of SpeciesRecording created with config dictionaries held by the caller.
        """

        recording_config = deepcopy(config["Recording"])

        preprocessor = utils.load_name_from_module(
            "pp",
            self.model_dir / Path(model_name) / "preprocessor.py",
            "Preprocessor",
        )(**self.preprocessor_config)

        model = utils.load_name_from_module(
            "mo", self.model_dir / Path(model_name) / "model.py", "Model"
        )(model_path=self.model_dir / model_name, **self.model_config)

        # process species range predictor
        if all(name in recording_config for name in ["date", "lat", "lon"]) and all(
            recording_config[name] is not None for name in ["date", "lat", "lon"]
        ):

            try:
                # we can use the species predictor
                species_predictor = SpeciesPredictorBase(
                    model_path=self.model_dir / model_name,
                    **config["SpeciesPredictor"],
                )

                recording_config["species_predictor"] = species_predictor

            except Exception as e:
                raise ValueError(
                    "An error occured during species range predictor creation. Does you model provide a model file called 'species_presence_model'?"
                ) from e

        # create recording object
        # species predictor is applied here once and then used for all the analysis calls that may follow
        return SparrowRecording(preprocessor, model, "", **recording_config)

    def __init__(
        self,
        indir: str,
        outdir: str,
        model_dir: str,
        model_name: str,
        preprocessor_config: dict = None,
        model_config: dict = None,
        recording_config: dict = None,
        species_predictor_config: dict = None,
        pattern: str = ".wav",
        check_time: int = 1,
        delete_recordings: str = "never",
    ):
        """
        __init__ Create a new Watcher object.

        Args:
            indir (str): Directory to read files from
            outdir (str): Directory to write the analysis results to.
                        A new directory with a timestamp for name will be
                        created within it to store the result files in.
            model_dir (str): Directory where downloaded models are stored
            model_name (str): name of the model to use. Must match the directory name it is stored in, e.g., 'birdnet_default'.
            preprocessor_config (dict, optional): Keyword arguments for the preprocessor of the model. Defaults to {}.
            model_config (dict, optional): Keyword arguments for the model instance. Defaults to {}.
            recording_config (dict, optional): Keyword arguments for the internal SparrowRecording. Defaults to {}.
            species_predictor_config (dict, optional): Keyword arguments for a species presence predictor model. Defaults to {}.
            pattern (str, optional): filename pattern to look for. defaults to '.wav'.
            check_time(int, optional): Sleep time of the watcher between checks for new files in seconds. Defaults to 1.
            delete_recordings(str, optional): Mode for data clean up. Can be one of "never" or "always".
                                            "never" keeps recordings around indefinitely. 'always' deletes the recording
                                            immediatelly after analysis. Defaults to 'never'.
        Raises:
            ValueError: When the indir parameter is not an existing directory.
            ValueError: When the outdir parameter is not an existing directory.
            ValueError: When the model_dir parameter is not an existing directory.
            ValueError: When the model name does not correspond to a directory in the 'model_dir' directory in which available models are stored.
        """

        # set up data to use
        self.input = Path(indir)

        if self.input.is_dir() is False:
            raise ValueError("Input directory does not exist")

        self.outdir = outdir

        if self.outdir.is_dir() is False:
            raise ValueError("Output directory does not exist")

        self.output = Path(self.outdir) / Path(datetime.now().strftime("%y%m%d_%H%M%S"))

        self.model_dir = Path(model_dir)

        if self.model_dir.is_dir() is False:
            raise ValueError("Model directory does not exist")

        if (self.model_dir / model_name).is_dir() is False:
            raise ValueError("Given model name does not exist in model directory")

        self.pattern = pattern

        self.model_name = model_name

        self.watcher_process = None

        self.may_do_work = multiprocessing.Event()

        self.is_done_analyzing = multiprocessing.Event()

        self.check_time = check_time

        if delete_recordings not in ["never", "always"]:
            raise ValueError("'delete_recordings' must be in 'never', 'always'")

        self.delete_recordings = delete_recordings

        if preprocessor_config is None:
            preprocessor_config = {}

        if model_config is None:
            model_config = {}

        if recording_config is None:
            recording_config = {}

        if species_predictor_config is None:
            species_predictor_config = {}

        self.preprocessor_config = deepcopy(preprocessor_config)

        self.model_config = deepcopy(model_config)

        self.recording_config = deepcopy(recording_config)

        self.species_predictor_config = deepcopy(species_predictor_config)

        self.first_analyzed_file = multiprocessing.Value(str, "")

        self.last_analyzed_file = multiprocessing.Value(str, "")

    @property
    def output_directory(self):
        return str(self.output)

    @property
    def input_directory(self):
        return str(self.input)

    @property
    def is_running(self):
        if self.watcher_process is not None:
            return self.watcher_process.is_alive()
        else:
            return False

    def analyze(self, filename: str, recording: SparrowRecording):
        """
        analyze Analyze a file pointed to by 'filename' and save the results as csv file to 'output'.

        Args:
            filename (str): path to the file to analyze.
            recording (SparrowRecording): recording object to use
        """
        self.may_do_work.wait()  # wait until parent process allows the worker to pick up work

        recording.path = filename

        recording.analyzed = False  # reactivate

        # make the main process wait on the finish signal to make sure no
        # corrupt files are produced
        self.is_done_analyzing.clear()

        recording.analyze()

        results = recording.detections

        self.save_results(self.output, results, suffix=Path(filename).stem)

        self.is_done_analyzing.set()  # give good-to-go for main process

        if self.delete_recordings == "always":
            Path(filename).unlink()

    def save_results(self, outfolder: str, results: list, suffix=""):
        """
        save_results Save results to csv file.

        Args:
            outfolder (str): folder to save the results in
            suffix (str, optional): _description_. Defaults to "".
        """

        with open(Path(outfolder) / Path(f"results_{suffix}.csv"), "w") as csvfile:
            if len(results) == 0:
                writer = csv.writer(csvfile)
                writer.writerow([])
            else:
                colnames = results[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=colnames)
                writer.writeheader()
                writer.writerows(results)

    def start(self):
        """
        start Watch the directory the caller has been created with and analyze all newly created files matching a certain file ending. \
            Creates a new daemon process in which the analysis function runs.

        Raises:
            RuntimeError: When the watcher process is running already.
        """
        if self.is_running:
            raise RuntimeError("watcher process still running, stop first.")

        self.output.mkdir(exist_ok=True, parents=True)

        self._write_config()

        try:
            print("start the watcher process")
            # create a background watchertask such that the command is handed back to the parent process

            self.may_do_work.set()
            self.is_done_analyzing.clear()
            self.watcher_process = multiprocessing.Process(
                target=watchertask, args=(self,)
            )
            self.watcher_process.daemon = True
            self.watcher_process.name = "watcher_process"
            self.watcher_process.start()
        except Exception as e:

            if self.output.is_dir():
                for filename in self.output.iterdir():
                    filename.unlink()
                self.output.rmdir()

            self.may_do_work.clear()
            self.is_done_analyzing.clear()
            self.watcher_process = None

            raise RuntimeError(
                "Something went wrong when starting the watcher process, undoing changes and returning"
            ) from e

    def restart(self):
        """
        restart Restart the watcher process. Must be called when, e.g., new models have been loaded or the input or output has changed.
        """
        print("trying to restart the watcher process")
        self.stop()
        self.start()

    def pause(self):
        """
        pause Pause the watcher process.

        Raises:
            RuntimeError: When the watcher process is not running.
        """
        if self.watcher_process is not None and self.watcher_process.is_alive():
            self.is_done_analyzing.wait()  # wait for the finish event
            self.may_do_work.clear()
        else:
            raise RuntimeError("Cannot pause watcher process, is not alive anymore.")

    def go_on(self):
        """
        go_on Continue the watcher thread.

        Raises:
            RuntimeError: When the watcher process is not running anymore
        """
        if self.watcher_process is not None and self.watcher_process.is_alive():
            print("continue the watcher process")
            self.may_do_work.set()
        else:
            raise RuntimeError("Cannot continue watcher process, is not alive anymore.")

    def stop(self):
        """
        stop Stop the watcher process if it is still running.

        Raises:
            RuntimeError: When the watcher process is not running anymore
        """
        if self.watcher_process is not None and self.watcher_process.is_alive():
            print("trying to stop the watcher process")
            flag_set = self.is_done_analyzing.wait(timeout=30)

            if flag_set is False:
                warnings.warn("stop timeout expired, terminating watcher process now.")

            try:
                self.watcher_process.terminate()
                self.watcher_process.join()
                self.watcher_process.close()
                self.watcher_process = None
                self.may_do_work.clear()
                self.is_done_analyzing.set()
            except Exception as e:
                raise RuntimeError(
                    "Something went wrong when trying to stop the watcher process"
                ) from e

        else:
            raise RuntimeError("Cannot stop watcher process, is not alive anymore.")

    def change_analyzer(
        self,
        model_name: str,
        preprocessor_config: dict = None,
        model_config: dict = None,
        recording_config: dict = None,
        species_predictor_config: dict = None,
        pattern: str = ".wav",
        check_time: int = 1,
        delete_recordings: str = "never",
    ):
        """
        change_analyzer Change classifier model to the one indicated by name.
        The given model name must correspond to the name of a folder in the
        iSparrow models directory created upon install.

        Args:
            model_name (str): Name of the model to be used
            preprocessor_config (dict, optional): Parameters for preprocessor given as key(str): value. If empty, default parameters of the preprocessor will be used. Defaults to {}.
            model_config (dict, optional): Parameters for the model given as key(str): value. If empty, default parameters of the model will be used. Defaults to {}.
            recording_config (dict, optional): Parameters for the underlyin SparrowRecording object. If empty, default parameters of the recording will be used. Defaults to {}.
            species_predictor_config (dict, optional): _description_. If empty, default parameters of the species predictor will be used. Defaults to {}.
            Make sure the model you use is compatible with a species predictor before supplying these.
            pattern (str, optional): filename pattern to look for. defaults to '.wav'.
            check_time(int, optional): Sleep time of the watcher between checks for new files in seconds. Defaults to 1.
            delete_recordings(str, optional): Mode for data clean up. Can be one of "never" or "always".
                                            "never" keeps recordings around indefinitely. 'always' deletes the recording
                                            immediatelly after analysis. Defaults to 'never'.

        Raises:
            ValueError: _description_
            RuntimeError: _description_
        """

        if self.watcher_process is None or self.is_running is False:
            raise RuntimeError("Watcher not running, cannot change analyzer")

        print("changing analyzer to: ", model_name)
        # import and build new model, pause the analyzer process,
        # change the model, resume the analyzer
        if preprocessor_config is None:
            preprocessor_config = {}

        if model_config is None:
            model_config = {}

        if recording_config is None:
            recording_config = {}

        if species_predictor_config is None:
            species_predictor_config = {}

        if (self.model_dir / model_name).is_dir() is False:
            raise ValueError("Given model name does not exist in model dir.")

        old_model_name = self.model_name
        old_preprocessor_config = deepcopy(self.preprocessor_config)
        old_model_config = deepcopy(self.model_config)
        old_recording_config = deepcopy(self.recording_config)
        old_species_predictor_config = deepcopy(self.species_predictor_config)
        old_pattern = deepcopy(self.pattern)
        old_check_time = self.check_time
        old_delete = self.delete_recordings

        self.model_name = model_name
        self.output = Path(self.outdir) / Path(datetime.now().strftime("%y%m%d_%H%M%S"))
        self.preprocessor_config = preprocessor_config
        self.model_config = model_config
        self.recording_config = recording_config
        self.species_predictor_config = species_predictor_config
        self.pattern = pattern
        self.check_time = check_time
        self.delete_recordings = delete_recordings

        # restart process to make changes take effect
        try:
            self.restart()
        except Exception as e:
            # restore state when something goes wrong
            self.model_name = old_model_name
            self.preprocessor_config = old_preprocessor_config
            self.model_config = old_model_config
            self.recording_config = old_recording_config
            self.species_predictor_config = old_species_predictor_config
            self.pattern = old_pattern
            self.check_time = old_check_time
            self.delete_recordings = old_delete

            self.may_do_work.clear()
            self.is_done_analyzing.set()
            self.output = Path(self.outdir) / Path(
                datetime.now().strftime("%y%m%d_%H%M%S")
            )
            if self.is_running:
                self.stop()

            raise RuntimeError(
                "Error when restarting the watcher process, any changes made have been undone. The process needs to be restarted manually. This operation may have led to data loss."
            ) from e

    def clean_up(self):
        """
        clean_up Go over previous folders and run analysis on any files that have not been analyzed before.
        """

        outputfolders = (
            folder
            for folder in self.outdir.iterdir()
            if (
                folder == self.output
                or not folder.is_dir()
                or (folder / "missings.txt").is_file()
            )
            is False
        )

        for outfolder in outputfolders:

            missings = []

            cfg = utils.read_yaml(outfolder / "config.yml")

            recording = self.set_up_recording(
                cfg["Analysis"]["Model"]["model_path"], cfg
            )

            input_folder = Path(cfg["Analysis"]["input"])

            audiofiles = (
                f
                for f in input_folder.iterdir()
                if f.suffix == cfg["Analysis"]["pattern"]
            )

            for audiofile in audiofiles:

                if (
                    outfolder / Path(f"results_{audiofile.stem}.csv")
                ).if_file() is False:

                    recording.path = audiofile
                    recording.analyzed = False  # reactivate
                    recording.analyze()
                    results = recording.detections
                    self.save_results(outfolder, results, suffix=audiofile.stem)
                    missings.append(audiofile)

                    if cfg["Analysis"]["delete_recordings"] == "always":
                        audiofile.unlink()

            with open(outfolder / "missings.txt", "w") as missingsfile:
                missingsfile.write(missings)
