import simvue
import typing
import platform
import pathlib
import pydantic
import glob
import os.path
import re
import os
import f90nml
import multiparser.parsing.tail as mp_tail_parser
import multiparser.parsing.file as mp_file_parser

from simvue_integrations.connectors.generic import WrappedRun


class FDSRun(WrappedRun):
    def _soft_abort(self):
        """
        If an abort is triggered, creates a '.stop' file so that FDS simulation is stopped gracefully.
        """
        if not os.path.exists(f"{self._results_prefix}.stop"):
            with open(f"{self._results_prefix}.stop", "w") as stop_file:
                stop_file.write("FDS simulation aborted due to Simvue Alert.")
                stop_file.close()

    @mp_tail_parser.log_parser
    def _log_parser(
        self, file_content: str, **__
    ) -> tuple[dict[str, typing.Any], list[dict[str, typing.Any]]]:
        """Parses an FDS log file line by line as it is written, and extracts relevant information

        Parameters
        ----------
        file_content : str
            The next line of the log file

        Returns
        -------
        tuple[dict[str,typing.Any], list[dict[str, typing.Any]]]
            An (empty) dictionary of metadata, and a dictionary of metrics data extracted from the log
        """

        _out_data = []
        _out_record = {}

        for line in file_content.split("\n"):
            for pattern in self._patterns:
                match = pattern["pattern"].search(line)
                if match:
                    if pattern["name"] == "step":
                        if _out_record:
                            _out_data += [_out_record]
                        _out_record = {}

                    _out_record[pattern["name"]] = match.group(1)

                    if pattern["name"] == "time":
                        self.log_event(
                            f"Time Step: {_out_record['step']}, Simulation Time: {_out_record['time']} s"
                        )

            if "DEVICE Activation Times" in line:
                self._activation_times = True
                print("DEVICE Activation Times")
            elif self._activation_times and "Time Stepping" in line:
                self._activation_times = False
            elif self._activation_times:
                match = re.match(r"\s+\d+\s+([\w]+)\s+\w+\s+([\d\.]+)\s*", line)
                if match:
                    self._activation_times_data[f"{match.group(1)}_activation_time"] = (
                        float(match.group(2))
                    )

        if _out_record:
            _out_data += [_out_record]

        return {}, _out_data

    def _metrics_callback(self, data: typing.Dict, meta: typing.Dict):
        """Log metrics extracted from a log file to Simvue.

        Parameters
        ----------
        data : typing.Dict
            Dictionary of data to log to Simvue as metrics
        meta: typing.Dict
            Dictionary of metadata added by Multiparser about this data
        """
        metric_time = data.pop("time", None) or data.pop("Time", None)
        metric_step = data.pop("step", None)
        self.log_metrics(
            data, timestamp=meta["timestamp"], time=metric_time, step=metric_step
        )

    @mp_file_parser.file_parser
    def _header_metadata(
        self, input_file: str, **__
    ) -> tuple[dict[str, typing.Any], list[dict[str, typing.Any]]]:
        """Parse metadata from header of FDS stderr output file.

        Parameters
        ----------
        input_file : str
            The path to the FDS stderr output file.
        """
        with open(input_file) as in_f:
            _file_lines = in_f.readlines()

        _components_regex: dict[str, typing.Pattern[typing.AnyStr]] = {
            "fds.revision": re.compile(r"^\s*Revision\s+\:\s*([\w\d\.\-\_][^\n]+)"),
            "fds.revision_date": re.compile(
                r"^\s*Revision Date\s+\:\s*([\w\s\:\d\-][^\n]+)"
            ),
            "fds.compiler": re.compile(
                r"^\s*Compiler\s+\:\s*([\w\d\-\_\(\)\s\.\[\]\,][^\n]+)"
            ),
            "fds.compilation_date": re.compile(
                r"^\s*Compilation Date\s+\:\s*([\w\d\-\:\,\s][^\n]+)"
            ),
            "fds.mpi_processes": re.compile(r"^\s*Number of MPI Processes:\s*(\d+)"),
            "fds.mpi_version": re.compile(r"^\s*MPI version:\s*([\d\.]+)"),
            "fds.mpi_library_version": re.compile(
                r"^\s*MPI library version:\s*([\w\d\.\s\*\(\)\[\]\-\_][^\n]+)"
            ),
        }

        _output_metadata: dict[str, str] = {}

        for line in _file_lines:
            for key, regex in _components_regex.items():
                if search_res := regex.findall(line):
                    _output_metadata[key] = search_res[0]

        return {}, _output_metadata

    def _ctrl_log_callback(self, data: typing.Dict, meta: typing.Dict):
        """Log metrics extracted from the CTRL log file to Simvue.

        Parameters
        ----------
        data : typing.Dict
            Dictionary of data from the latest line of the CTRL log file.
        meta: typing.Dict
            Dictionary of metadata added by Multiparser about this data.
        """
        if data["State"].lower() == "f":
            state = False
        elif data["State"].lower() == "t":
            state = True
        else:
            state = data["State"]

        event_str = f"{data['Type']} '{data['ID']}' has been set to '{state}' at time {data['Time (s)']}s"
        if data.get("Value"):
            event_str += (
                f", when it reached a value of {data['Value']}{data.get('Units', '')}."
            )

        self.log_event(event_str)
        self.update_metadata({data["ID"]: state})

    def _pre_simulation(self):
        """Starts the FDS process, using a bash script to set `fds_unlim` if on Linux"""
        super()._pre_simulation()
        self.log_event("Starting FDS simulation")

        fds_unlim_path = (
            pathlib.Path(__file__).parents[1].joinpath("extras", "fds_unlim")
        )
        executable = f"{fds_unlim_path}" if platform.system() != "Windows" else "fds"

        self.add_process(
            "fds_simulation",
            executable=executable,
            input_file=self.fds_input_file_path,
            cwd=self.workdir_path,
            completion_trigger=self._trigger,
            ulimit=self.ulimit,
            **self.fds_env_vars,
        )

    def _during_simulation(self):
        """Describes which files should be monitored during the simulation by Multiparser"""
        # Upload data from input file as metadata
        self.file_monitor.track(
            path_glob_exprs=str(self.fds_input_file_path),
            callback=lambda data, meta: self.update_metadata(
                {k: v for k, v in data.items() if v}
            ),
            file_type="fortran",
            static=True,
        )
        # Upload metadata from file header
        self.file_monitor.track(
            path_glob_exprs=f"{self._results_prefix}.out",
            parser_func=self._header_metadata,
            callback=lambda data, meta: self.update_metadata({**data, **meta}),
            static=True,
        )
        self.file_monitor.tail(
            path_glob_exprs=f"{self._results_prefix}.out",
            parser_func=self._log_parser,
            callback=self._metrics_callback,
        )
        self.file_monitor.tail(
            path_glob_exprs=f"{self._results_prefix}_hrr.csv",
            parser_func=mp_tail_parser.record_csv,
            parser_kwargs={"header_pattern": "Time"},
            callback=self._metrics_callback,
        )
        self.file_monitor.tail(
            path_glob_exprs=f"{self._results_prefix}_devc.csv",
            parser_func=mp_tail_parser.record_csv,
            parser_kwargs={"header_pattern": "Time"},
            callback=self._metrics_callback,
        )
        self.file_monitor.tail(
            path_glob_exprs=f"{self._results_prefix}_devc_ctrl_log.csv",
            parser_func=mp_tail_parser.record_csv,
            callback=self._ctrl_log_callback,
        )

    def _post_simulation(self):
        """Uploads files selected by user to Simvue for storage."""
        self.update_metadata(self._activation_times_data)

        if self.upload_files is None:
            for file in glob.glob(f"{self._results_prefix}*"):
                if os.path.abspath(file) == os.path.abspath(self.fds_input_file_path):
                    continue
                self.save_file(file, "output")
        else:
            if self.workdir_path:
                self.upload_files = [
                    str(os.path.join(self.workdir_path, path))
                    for path in self.upload_files
                ]

            for path in self.upload_files:
                for file in glob.glob(path):
                    if os.path.abspath(file) == os.path.abspath(
                        self.fds_input_file_path
                    ):
                        continue
                    self.save_file(file, "output")

        super()._post_simulation()

    @simvue.utilities.prettify_pydantic
    @pydantic.validate_call
    def launch(
        self,
        fds_input_file_path: pydantic.FilePath,
        workdir_path: typing.Union[str, pydantic.DirectoryPath] = None,
        upload_files: list[str] = None,
        ulimit: typing.Union[str, int] = "unlimited",
        fds_env_vars: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ):
        """Command to launch the FDS simulation and track it with Simvue.

        Parameters
        ----------
        fds_input_file_path : pydantic.FilePath
            Path to the FDS input file to use in the simulation
        workdir_path : str, optional
            Path to a directory which you would like FDS to run in, by default None
            This is where FDS will generate the results from the simulation
            If a directory does not already exist at this path, it will be created
            Uses the current working directory by default.
        upload_files : list[str], optional
            List of results file names to upload to the Simvue server for storage, by default None
            These should be supplied as relative to the working directory specified above (if specified, otherwise relative to cwd)
            If not specified, will upload all files by default. If you want no results files to be uploaded, provide an empty list.
        ulimit : typing.Union[str, int], optional
            Value to set your stack size to (for Linux and MacOS), by default "unlimited"
        fds_env_vars : typing.Optional[typing.Dict[str, typing.Any]], optional
            Environment variables to provide to FDS when executed, by default None
        """
        self.fds_input_file_path = fds_input_file_path
        self.workdir_path = workdir_path
        self.upload_files = upload_files
        self.ulimit = ulimit
        self.fds_env_vars = fds_env_vars or {}

        self._patterns = [
            {"pattern": re.compile(r"\s+Time\sStep\s+(\d+).*"), "name": "step"},
            {
                "pattern": re.compile(r"\s+Step\sSize:.*Total\sTime:\s+([\d\.]+)\ss.*"),
                "name": "time",
            },
            {
                "pattern": re.compile(r"\s+Pressure\sIterations:\s(\d+)$"),
                "name": "pressure_iteration",
            },
            {
                "pattern": re.compile(
                    r"\s+Maximum\sVelocity\sError:\s+([\d\.\-\+E]+)\son\sMesh\s\d+\sat\s\(\d+,\d+,\d+\)$"
                ),
                "name": "max_velocity_error",
            },
            {
                "pattern": re.compile(
                    r"\s+Maximum\sPressure\sError:\s+([\d\.\-\+E]+)\son\sMesh\s\d+\sat\s\(\d+,\d+,\d+\)$"
                ),
                "name": "max_pressure_error",
            },
            {
                "pattern": re.compile(
                    r"\s+Max\sCFL\snumber:\s+([\d\.E\-\+]+)\sat\s\(\d+,\d+,\d+\)$"
                ),
                "name": "max_cfl",
            },
            {
                "pattern": re.compile(
                    r"\s+Max\sdivergence:\s+([\d\.E\-\+]+)\sat\s\(\d+,\d+,\d+\)$"
                ),
                "name": "max_divergence",
            },
            {
                "pattern": re.compile(
                    r"\s+Min\sdivergence:\s+([\d\.E\-\+]+)\sat\s\(\d+,\d+,\d+\)$"
                ),
                "name": "min_divergence",
            },
            {
                "pattern": re.compile(
                    r"\s+Max\sVN\snumber:\s+([\d\.E\-\+]+)\sat\s\(\d+,\d+,\d+\)$"
                ),
                "name": "max_vn",
            },
            {
                "pattern": re.compile(r"\s+No.\sof\sLagrangian\sParticles:\s+(\d+)$"),
                "name": "num_lagrangian_particles",
            },
            {
                "pattern": re.compile(
                    r"\s+Total\sHeat\sRelease\sRate:\s+([\d\.\-]+)\skW$"
                ),
                "name": "total_heat_release_rate",
            },
            {
                "pattern": re.compile(
                    r"\s+Radiation\sLoss\sto\sBoundaries:\s+([\d\.\-]+)\skW$"
                ),
                "name": "radiation_loss_to_boundaries",
            },
        ]
        self._activation_times = False
        self._activation_times_data = {}

        nml = f90nml.read(self.fds_input_file_path)
        self._chid = nml["head"]["chid"]

        if self.workdir_path:
            os.makedirs(self.workdir_path, exist_ok=True)

            for file in glob.glob(os.path.join(self.workdir_path, f"{self._chid}*")):
                if os.path.abspath(file) == os.path.abspath(self.fds_input_file_path):
                    continue
                os.remove(file)

        self._results_prefix = (
            str(os.path.join(self.workdir_path, self._chid))
            if self.workdir_path
            else self._chid
        )

        super().launch()
