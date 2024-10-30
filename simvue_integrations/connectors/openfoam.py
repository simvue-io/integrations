import simvue
import typing
import pydantic
import multiparser.parsing.tail as mp_tail_parser
import os
import re
import zipfile
from simvue_integrations.connectors.generic import WrappedRun


class OpenfoamRun(WrappedRun):
    def _save_directory(
        self,
        dir_names: list[str],
        zip_name: str,
        file_type: typing.Literal["input", "output", "code"],
    ):
        """Save directories of files to the Simvue run.

        If upload_to_zip is True, will add files from all of the directories provided to a single archive Zip file,
        and then upload this file to Simvue.

        If upload_to_zip is False, will upload each file in the directories individually to Simvue.

        Parameters
        ----------
        dir_names : list[str]
            List of directories wihtin the case directory to save to the Simvue run
        zip_name : str
            Name of the zip file to create, if upload_to_zip is True
        file_type : typing.Literal["input", "output", "code"]
            The category of files being uploaded
        """

        if self.upload_as_zip:
            out_zip = os.path.join(self.openfoam_case_dir, zip_name)
            zip_file = zipfile.ZipFile(out_zip, "w")

        for dir_name in dir_names:
            dir_path = os.path.join(self.openfoam_case_dir, dir_name)

            if not os.path.exists(dir_path):
                return

            # Go through directory recursively, either add each file to the zip, or upload individually to Simvue
            for root, _, file_names in os.walk(dir_path):
                for file_name in file_names:
                    file_path = os.path.join(root, file_name)
                    if not file_path:
                        continue
                    if self.upload_as_zip:
                        zip_file.write(
                            file_path,
                            os.path.relpath(file_path, self.openfoam_case_dir),
                        )
                    else:
                        self.save_file(
                            file_path,
                            file_type,
                            name=str(
                                os.path.relpath(file_path, self.openfoam_case_dir)
                            ),
                        )

        if self.upload_as_zip:
            zip_file.close()
            self.save_file(out_zip, file_type)
            os.remove(out_zip)

    @mp_tail_parser.log_parser
    def _log_parser(
        self, file_content: str, **__
    ) -> tuple[dict[str, typing.Any], dict[str, typing.Any]]:
        """Parses information from any Openfoam log file, and uploads key data to Simvue.

        Uploads information from the header of the file as Metadata to the Run, uploads log messages from the file
        which are produced before the solve begins as Events, and then uploads residuals values as Metrics.

        Parameters
        ----------
        file_content : str
            The latest additions to the file.

        Returns
        -------
        tuple[dict[str,typing.Any], dict[str, typing.Any]]
            An (empty) dictionary of metadata, and a dictionary of any metrics obtained from the file.
        """

        exp1: re.Pattern[str] = re.compile(
            r"^(.+):  Solving for (.+), Initial residual = (.+), Final residual = (.+), No Iterations (.+)$"
        )
        exp2: re.Pattern[str] = re.compile(r"^ExecutionTime = ([0-9.]+) s")
        metrics = {}
        header_metadata = {}
        title = False
        header = False
        solver_info = False

        for line in file_content.splitlines():
            # Determine where we are in the file
            if line.startswith("/*-"):
                self.log_event("Starting new execution...")
                title = True
                header = False
                solver_info = False
            if line.startswith("\*-"):
                title = False
                header = True
                solver_info = False
                continue
            elif line.startswith("// *"):
                title = False
                header = False
                if not self.metadata_uploaded:
                    self.update_metadata(header_metadata)
                    self.metadata_uploaded = True
                solver_info = True
                continue

            # Get metrics
            match = exp1.match(line)
            if match:
                # We must be outside the title, header and initial solver info if matched regex pattern
                title = False
                header = False
                solver_info = False

                metrics["residuals.initial.%s" % match.group(2)] = match.group(3)
                metrics["residuals.final.%s" % match.group(2)] = match.group(4)

            if title:
                continue

            # Store header data
            if header:
                # Ignore blank lines
                if not line:
                    continue
                key, value = line.split(":", 1)
                key = key.strip().replace(" ", "_").replace("/", "-").lower()
                value = value.strip()
                # If the line corresponds to the 'exec' parameter, store this as an event instead of a piece of metadata
                # since we will be storing data from multiple log files which are executing different things
                if key == "exec":
                    current_process = value
                else:
                    header_metadata[f"openfoam.{key}"] = value

            # Log events for any initial solver info
            if solver_info and line:
                self.log_event(f"[{current_process}]: {line}")

            # Get time, store metrics
            match = exp2.match(line)
            if match:
                ttime = match.group(1)
                if metrics:
                    self.log_metrics(metrics, time=ttime)
                    metrics = {}

        return {}, metrics

    def pre_simulation(self):
        """Uploads inputs from the system, constant and 0 directories, and adds the Openfoam process."""
        super().pre_simulation()

        # Save the files in the System, Constant, and initial conditions ('0') directories
        self._save_directory(["system", "constant", "0"], "inputs.zip", "input")

        # TODO: Any alerts I should define?

        # Add the Openfoam simulation as a process
        self.add_process(
            identifier="openfoam_simulation",
            executable="/bin/sh",
            script=str(os.path.join(self.openfoam_case_dir, "Allrun")),
            completion_trigger=self._trigger,
            **self.openfoam_env_vars,
        )

    def during_simulation(self):
        """Tracks any log files produced by Openfoam."""
        # Track all log files
        self.file_monitor.tail(
            parser_func=self._log_parser,
            path_glob_exprs=[os.path.join(self.openfoam_case_dir, "log.*")],
            callback=lambda *_, **__: None,
        )

    def post_simulation(self):
        """Uploads all results found in the Openfoam case directory."""
        reg_exp = re.compile(r"([\d\.]+)")
        result_dirs = [
            dir_name
            for dir_name in os.listdir(self.openfoam_case_dir)
            if reg_exp.match(dir_name)
        ]
        self._save_directory(result_dirs, "results.zip", "output")

        super().post_simulation()

    @simvue.utilities.prettify_pydantic
    @pydantic.validate_call
    def launch(
        self,
        openfoam_case_dir: pydantic.DirectoryPath,
        upload_as_zip: bool = True,
        openfoam_env_vars: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ):
        """Command to launch the Openfoam simulation and track it with Simvue.

        Parameters
        ----------
        openfoam_case_dir : pydantic.DirectoryPath
            The path to the directory containing the openfoam case (containing an Allrun file, and input directories)
        upload_as_zip : bool, optional
            Whether to upload inputs and outputs as zip files, by default True
        openfoam_env_vars : typing.Optional[typing.Dict[str, typing.Any]], optional
            A dictionary of any environment variables to pass to the Openfoam simulation, by default None
        """
        self.openfoam_case_dir = openfoam_case_dir
        self.upload_as_zip = upload_as_zip
        self.openfoam_env_vars = openfoam_env_vars or {}
        self.metadata_uploaded = False

        super().launch()
