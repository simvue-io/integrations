import simvue
import typing
import pydantic
import multiparser
import multiparser.parsing.file as mp_file_parser
import multiparser.parsing.tail as mp_tail_parser
import os
import multiprocessing
import time
import re

@mp_file_parser.file_parser
def _moose_header_parser(
    input_file: str,
    **_) -> typing.Dict[str, str]:
    """Method which parses the header of the MOOSE log file and returns the data from it as a dictionary.

    Parameters
    ----------
    input_file : str
        The path to the file where the console log is stored.

    Returns
    -------
    typing.Dict[str, str]
        The parsed data from the header of the MOOSE log file
    """
    # Open the log file, and read lines 1-7 (which contains information about the MOOSE version used etc)
    with open(input_file) as file:
        file_lines = file.readlines()
    file_lines = list(filter(None, file_lines))

    # Add the data from each line of the header into a dictionary as a key/value pair
    header_data = {}
    for line in file_lines:
        # Ignore blank lines
        if not line.strip():
            continue
        key, value = line.split(":", 1)
        # Ignore lines which correspond to 'titles'
        if not value:
            continue
        value = value.strip()
        if not value:
            continue
        header_data[key] = value

    return {}, header_data
class MooseRun(simvue.Run):
    def _per_event_callback(self, log_data, _):
        """_summary_

        Parameters
        ----------
        log_data : _type_
            _description_
        _ : _type_
            _description_

        Returns
        -------
        _type_
            _description_
        """

        # Look for relevant keys in the dictionary of data which we are passed in, and log the event with Simvue
        if any(key in ("time_step", "converged", "non_converged", "finished") for key in log_data.keys()):
            try:
                self.log_event(list(log_data.values())[0])
            except RuntimeError as e:
                self._error(e)
                return False

        if "time_step" in log_data.keys():
            self._time = time.time()
        
        elif "converged" in log_data.keys():
            self.log_event(f"Step calculation time: {round((time.time() - self._time), 2)} seconds.")
        
        # If simulation has completed successfully, save outputs, close the run, terminate multiparser
        elif "finished" in log_data.keys():
            time.sleep(1) # To allow other processes to complete

            if os.path.exists(os.path.join(self.output_dir_path, f"{self.results_prefix}.e")):
                self.save_file(os.path.join(self.output_dir_path, f"{self.results_prefix}.e"), "output")
            
            self._trigger.set()

    def _per_metric_callback(self, csv_data, sim_metadata):
        """Monitor each line in the results CSV file, and add data from it to Simvue Metrics."""

        metric_time = csv_data.pop('time')

        # Log all results for this timestep as Metrics
        self.log_metrics(
            csv_data,
            time = metric_time,
            timestamp = sim_metadata['timestamp']
        )
    @pydantic.validate_call
    def launch(
        self, 
        moose_application_path: pydantic.FilePath,
        moose_file_path: pydantic.FilePath,
        output_dir_path: str, # as this might not exist yet
        results_prefix: str,
        moose_env_vars: typing.Optional[typing.Dict[str, typing.Any]] = None
        ):

        self.moose_application_path = moose_application_path
        self.moose_file_path = moose_file_path
        self.output_dir_path = output_dir_path
        self.results_prefix = results_prefix
        self._trigger = multiprocessing.Event()
        self.moose_env_vars = moose_env_vars or {}

        if not self._simvue:
            self._error("Run must be initialized before launching the simulation.")
            return False

        # Add the MOOSE simulation as a process, so that Simvue can abort it if alerts begin to fire
        self.add_process(
            identifier='moose_simulation',
            executable=str(self.moose_application_path),
            i=str(self.moose_file_path),
            color="off",
            **self.moose_env_vars
            )
            
        # Add alert for a non converging step
        self.create_alert(
            name='step_not_converged',
            source='events',
            frequency=1,
            pattern=' Solve Did NOT Converge!',
            notification='email'
            )
            
        # Save the MOOSE file for this run to the Simvue server
        self.save_file(self.moose_file_path, "code")   

        # Start an instance of the file monitor, to keep track of log and results files from MOOSE
        with multiparser.FileMonitor(
            termination_trigger=self._trigger,
        ) as file_monitor:
            # Read the initial information within the log file when it is first created, to parse the header information
            file_monitor.track(
                path_glob_exprs = os.path.join(self.output_dir_path, f"{self.results_prefix}.txt"), 
                callback = lambda header_data, metadata: self.update_metadata({**header_data, **metadata}), 
                parser_func = _moose_header_parser, 
                static = True,
            )
            # Monitor each line added to the MOOSE log file as the simulation proceeds and look out for certain phrases to upload to Simvue
            file_monitor.tail(
                path_glob_exprs = os.path.join(self.output_dir_path, f"{self.results_prefix}.txt"), 
                callback = self._per_event_callback,
                tracked_values = [re.compile(r"Time Step.*"), " Solve Converged!", " Solve Did NOT Converge!", "Finished Executing"], 
                labels = ["time_step", "converged", "non_converged", "finished"]
            )
            # Monitor each line added to the MOOSE results file as the simulation proceeds, and upload results to Simvue
            file_monitor.tail(
                path_glob_exprs =  os.path.join(self.output_dir_path, f"{self.results_prefix}.csv"),
                parser_func = mp_tail_parser.record_csv,
                callback = self._per_metric_callback
            )
            file_monitor.run()

with MooseRun() as run:
    run.init(
        name="testing_moose_wrapper_1",
    )
    run.update_metadata({"test": 123})
    run.launch(
        moose_application_path='app/moose_tutorial-opt',
        moose_file_path=os.path.join(os.path.dirname(__file__), 'example', 'steel_mug.i'),
        output_dir_path=os.path.join(os.path.dirname(__file__), 'example', 'results', 'steel'),
        results_prefix="mug_thermal",
    )
    run.log_event("Simulation is finished!")
    run.update_tags(["converged"])