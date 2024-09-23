import simvue
import typing
import pydantic
import multiparser.parsing.file as mp_file_parser
import multiparser.parsing.tail as mp_tail_parser
import os
import time
import re
import csv
from simvue_integrations.connectors.generic import WrappedRun
from simvue_integrations.extras.create_command import format_command_env_vars   
            
class MooseRun(WrappedRun):
    """Class for setting up Simvue tracking and monitoring of a MOOSE simulation.

    Use this class as a context manager, in the same way you use default Simvue runs, and call run.launch(). Eg:

    with MooseRun() as run:
        run.init(
            name="moose_simulation",
        )
        run.launch(...)
    """        
    @mp_file_parser.file_parser
    def _moose_header_parser(
        self,
        input_file: str,
        **__) -> typing.Dict[str, str]:
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
        # Open the log file, and read header lines (which contains information about the MOOSE version used etc)
        with open(input_file) as file:
            file_lines = file.readlines()
        file_lines = list(filter(None, file_lines))

        # Add the data from each line of the header into a dictionary as a key/value pair
        header_data = {}
        for line in file_lines:
            # Ignore blank lines and lines which don't contain a colon
            if not line.strip() or ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            key = key.replace(" ","_").lower()
            # Replace any characters which will fail server side validation of key name with dashes
            key = re.sub('[^\w\-\s\.]+', '-', key)
            # Ignore lines which correspond to 'titles'
            if not value:
                continue
            value = value.strip()
            if not value:
                continue
            header_data[key] = value

        return {}, header_data
    @mp_file_parser.file_parser
    def _vector_postprocessor_parser(
        self,
        input_file: str,
        **__,
        ) -> typing.Dict[str, str]:
        """Parser for reading data from VectorPostProcessor CSV files

        Parameters
        ----------
        input_file : str
            Path to the VectorPostProcessor CSV file

        Returns
        -------
        typing.Dict[str, str]
            A dictionary of metadata and data contained in the CSV file
        """
        metrics = {}
        # Get name of vector which is being calculated by VectorPostProcessor from filename
        file_name = os.path.basename(input_file)
        vector_name, serial_num = file_name.replace(f"{self.results_prefix}_","").rsplit("_", 1)
        
        # If user has enabled time_data in their MOOSE file, get latest line from this file and save time
        time_file = f"{input_file.rsplit('_', 1)[0]}_time.csv"
        if os.path.exists(time_file):
            with open(time_file, newline="\n") as in_t:
                final_line = [in_t.readlines()[-1]]
                current_time_data = next(csv.reader(final_line))
                metrics['time'] = current_time_data[0]
                metrics['step'] = current_time_data[1]
        else:
            metrics['step'] = int(serial_num.split(".")[0])
            
        with open(input_file, newline="") as in_f:
            read_csv = csv.DictReader(in_f)
        
            for csv_data in read_csv:
                # Remove 'id' parameter if it exists, since we don't need it
                csv_data.pop('id', None)
                
                if radius := csv_data.pop('radius', None):
                    metrics.update({f"{vector_name}.{key}.r={radius}":value for (key, value) in csv_data.items()})
                elif (x := csv_data.pop('x', None)) is not None and (y := csv_data.pop('y', None)) is not None and (z := csv_data.pop('z', None)) is not None:
                    metrics.update({f"{vector_name}.{key}.x={x}_y={y}_z={z}":value for (key, value) in csv_data.items()})
                    
        return {}, metrics
    
    def _per_event_callback(self, log_data: typing.Dict[str, str], _):
        """Method which looks out for certain phrases in the MOOSE log, and adds them to the Events log

        Parameters
        ----------
        log_data : typing.Dict[str, str]
            Phrases of interest identified by the file monitor
        Returns
        -------
        bool
            Returns False if unable to upload events, to signal an error
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

            step_time = re.search(r"Time Step (\d+), time = (\d+), dt = .*", log_data["time_step"])
            if step_time:
                self._step_num = int(step_time.group(1))
                self._step_time = float(step_time.group(2))
        
        elif "converged" in log_data.keys():
            self.log_event(f" Step calculation time: {round((time.time() - self._time), 2)} seconds.")
            self.log_event(f" Total Nonlinear Iterations: {self._nonlinear}.")
            self.log_event(f" Total Linear Iterations: {self._linear}.")

            self.log_metrics(
                {
                    "total_linear_iterations": self._linear,
                    "total_nonlinear_iterations": self._nonlinear
                },
                self._step_num,
                self._step_time
            )

            self._linear = 0
            self._nonlinear = 0

        # Keep track of total number of linear and nonlinear iterations in the solve
        elif "nonlinear" in log_data.keys():
            self._nonlinear += 1
        elif "linear" in log_data.keys():
            self._linear += 1
        
        # If simulation has completed successfully, terminate multiparser
        elif "finished" in log_data.keys():
            time.sleep(1) # To allow other processes to complete
            self._trigger.set()

    def _per_metric_callback(self, csv_data: typing.Dict[str, float], sim_metadata: typing.Dict[str, str]):
        """Monitor each line in the results CSV file, and add data from it to Simvue Metrics.

        Parameters
        ----------
        csv_data : typing.Dict[str, float]
            The data from the latest line in the CSV file
        sim_metadata : typing.Dict[str, str]
            The metadata about when this line was read by Multiparser
        """
        metric_time = csv_data.pop('time', None)
        metric_step = csv_data.pop('step', None)

        # Log all results for this timestep as Metrics
        self.log_metrics(
            csv_data,
            step = metric_step or self._step_num,
            time = metric_time,
            timestamp = sim_metadata['timestamp']
        )

    def pre_simulation(self):
        """Simvue commands which are ran before the MOOSE simulation begins.
        """
        super().pre_simulation()

        # Add alert for a non converging step
        self.create_alert(
            name='step_not_converged',
            source='events',
            frequency=1,
            pattern=' Solve Did NOT Converge!',
            notification='email'
            )

        # Save the MOOSE file for this run to the Simvue server
        if os.path.exists(self.moose_file_path):
            self.save_file(self.moose_file_path, "input") 

        # Save the MOOSE Makefile
        if os.path.exists(os.path.join(os.path.dirname(self.moose_application_path), "Makefile")):
            self.save_file(os.path.join(os.path.dirname(self.moose_application_path), "Makefile"), 'input')

        # Add the MOOSE simulation as a process, so that Simvue can abort it if alerts begin to fire
        command = []
        if self.run_in_parallel:
            command += ['mpiexec', '-n', str(self.num_processors)]
            command += format_command_env_vars(self.mpiexec_env_vars)
        command += [str(self.moose_application_path), '-i', str(self.moose_file_path), '--color', 'off']
        command += format_command_env_vars(self.moose_env_vars)
        
        self.add_process(
            'moose_simulation',
            *command,
            completion_trigger=self._trigger,
            )
    
    def during_simulation(self):
        """Describes which files should be monitored during the simulation by Multiparser
        """
        self.log_event("Beginning MOOSE simulation...")
        # Record time here, for that for static problems the overall time for execution will be returned
        self._time = time.time()
        # This represents the step number and time of the step, ie when MOOSE says 'Time Step X, time = Y'
        self._step_num = 0
        self._step_time = 0
        # Initialize counters for keeping track of the number of linear and nonlinear steps involved in each solve
        self._nonlinear = 0
        self._linear = 0

        # Read the initial information within the log file when it is first created, to parse the header information
        self.file_monitor.track(
            path_glob_exprs = os.path.join(self.output_dir_path, f"{self.results_prefix}.txt"),
            callback = lambda header_data, metadata: self.update_metadata({**header_data, **metadata}), 
            parser_func = self._moose_header_parser, 
            static = True,
        )
        # Monitor each line added to the MOOSE log file as the simulation proceeds and look out for certain phrases to upload to Simvue
        self.file_monitor.tail(
            path_glob_exprs = os.path.join(self.output_dir_path, f"{self.results_prefix}.txt"), 
            callback = self._per_event_callback,
            tracked_values = [re.compile(r"Time Step.*"), " Solve Converged!", " Solve Did NOT Converge!", "Finished Executing", re.compile(r" \d+ Nonlinear \|R\|"), re.compile(r"     \d+ Linear \|R\|")], 
            labels = ["time_step", "converged", "non_converged", "finished", "nonlinear", "linear"]
        )
        # Monitor each line added to the MOOSE results file as the simulation proceeds, and upload results to Simvue
        self.file_monitor.tail(
            path_glob_exprs =  os.path.join(self.output_dir_path, f"{self.results_prefix}.csv"),
            parser_func = mp_tail_parser.record_csv,
            callback = self._per_metric_callback
        )
        self.file_monitor.exclude(os.path.join(self.output_dir_path, f"{self.results_prefix}_*_time.csv"))
        # Monitor each file created by a Vector PostProcessor, and upload results to Simvue if file matches an expected form.
        self.file_monitor.track(
            path_glob_exprs =  os.path.join(self.output_dir_path, f"{self.results_prefix}_*.csv"),
            parser_func = self._vector_postprocessor_parser,
            callback = self._per_metric_callback,
            static=True
        )

    def post_simulation(self):
        """Simvue commands which are ran after the MOOSE simulation finishes.
        """
        if os.path.exists(os.path.join(self.output_dir_path, f"{self.results_prefix}.e")):
            self.save_file(os.path.join(self.output_dir_path, f"{self.results_prefix}.e"), "output")
    
    @simvue.utilities.prettify_pydantic
    @pydantic.validate_call
    def launch(
        self, 
        moose_application_path: pydantic.FilePath,
        moose_file_path: pydantic.FilePath,
        output_dir_path: str, # as this might not exist yet
        results_prefix: str,
        run_in_parallel: bool = False,
        num_processors: int = 1,
        mpiexec_env_vars: typing.Optional[typing.Dict[str, typing.Any]] = None,
        moose_env_vars: typing.Optional[typing.Dict[str, typing.Any]] = None
        ):
        """Command to launch the MOOSE simulation and track it with Simvue.

        Parameters
        ----------
        moose_application_path : pydantic.FilePath
            Path to the MOOSE application file
        moose_file_path : pydantic.FilePath
            Path to the MOOSE configuration file
        output_dir_path : str
            The output directory where results and logs from MOOSE will be stored
        moose_env_vars : typing.Optional[typing.Dict[str, typing.Any]], optional
            Any environment variables to be passed to MOOSE on startup, by default None
        """

        self.moose_application_path = moose_application_path
        self.moose_file_path = moose_file_path
        self.output_dir_path = output_dir_path
        self.results_prefix = results_prefix
        self.run_in_parallel = run_in_parallel
        self.num_processors = num_processors
        self.mpiexec_env_vars = mpiexec_env_vars or {}
        self.moose_env_vars = moose_env_vars or {}

        super().launch()