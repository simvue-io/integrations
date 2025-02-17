"""OpenFOAM Connector.

This module provides functionality for using Simvue to track and monitor an OpenFOAM simulation.
"""

import os
import pathlib
import re
import typing
import zipfile

import multiparser.parsing.tail as mp_tail_parser
import pydantic
import simvue

from simvue_integrations.connectors.generic import WrappedRun


class OpenfoamRun(WrappedRun):
    """Class for setting up Simvue tracking and monitoring of an OpenFOAM simulation.

    Use this class as a context manager, in the same way you use default Simvue runs, and call run.launch(). Eg:

    with OpenfoamRun() as run:
        run.init(
            name="openfoam_simulation",
        )
        run.launch(...)
    """

    openfoam_case_dir: pydantic.DirectoryPath = None
    upload_as_zip: bool = None
    openfoam_env_vars: typing.Dict[str, typing.Any] = None

    _metadata_uploaded: bool = None

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
            out_zip = pathlib.Path(self.openfoam_case_dir).joinpath(zip_name)
            zip_file = zipfile.ZipFile(out_zip, "w")

        for dir_name in dir_names:
            dir_path = pathlib.Path(self.openfoam_case_dir).joinpath(dir_name)

            if not pathlib.Path(dir_path).exists():
                print(f"WARNING: Could not find directory {dir_path} - skipping!")
                continue

            # Go through directory recursively, either add each file to the zip, or upload individually to Simvue
            for root, _, file_names in os.walk(
                dir_path
            ):  # Using os.walk() as pathlib.Path.walk() only available in >=3.12
                for file_name in file_names:
                    file_path = pathlib.Path(root).joinpath(file_name)
                    if not file_path:
                        continue
                    if self.upload_as_zip:
                        zip_file.write(
                            file_path,
                            pathlib.Path(file_path).relative_to(self.openfoam_case_dir),
                        )
                    else:
                        self.save_file(
                            file_path,
                            file_type,
                            name=str(
                                pathlib.Path(file_path).relative_to(
                                    self.openfoam_case_dir
                                )
                            ),
                        )

        if self.upload_as_zip:
            zip_file.close()
            self.save_file(out_zip, file_type)
            pathlib.Path(out_zip).unlink()

    @mp_tail_parser.log_parser
    def _log_parser(
        self, file_content: str, **__
    ) -> tuple[dict[str, typing.Any], dict[str, typing.Any]]:
        """Parse information from any Openfoam log file, and uploads key data to Simvue.

        Uploads information from the header of the file as Metadata to the Run, uploads log messages from the file
        which are produced before the solve begins as Events, and then uploads residuals values as Metrics.

        Parameters
        ----------
        file_content : str
            The latest additions to the file.
        **__
            Additional unused keyword arguments

        Returns
        -------
        tuple[dict[str, typing.Any], dict[str, typing.Any]]
            An (empty) dictionary of metadata, and a dictionary of any metrics obtained from the file.

        """
        exp1: re.Pattern[str] = re.compile(
            r"^(.+):  Solving for (.+), Initial residual = (.+), Final residual = (.+), No Iterations (.+)$"
        )
        exp2: re.Pattern[str] = re.compile(r"^ExecutionTime = ([0-9.]+) s")
        metrics = {}
        header_metadata = {"openfoam": {}}
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
            if line.startswith("\\*-"):
                title = False
                header = True
                solver_info = False
                continue
            elif line.startswith("// *"):
                title = False
                header = False
                if not self._metadata_uploaded:
                    self.update_metadata(header_metadata)
                    self._metadata_uploaded = True
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
                    header_metadata["openfoam"][key] = value

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

    def _pre_simulation(self):
        """Upload inputs from the system, constant and 0 directories, and adds the Openfoam process."""
        super()._pre_simulation()

        # Save the files in the System, Constant, and initial conditions ('0') directories
        self._save_directory(["system", "constant", "0"], "inputs.zip", "input")

        # TODO: Any alerts I should define?

        # Add the Openfoam simulation as a process
        self.add_process(
            identifier="openfoam_simulation",
            executable="/bin/sh",
            script=str(pathlib.Path(self.openfoam_case_dir).joinpath("Allrun")),
            completion_trigger=self._trigger,
            **self.openfoam_env_vars,
        )

    def _during_simulation(self):
        """Track any log files produced by Openfoam."""
        # Track all log files
        self.file_monitor.tail(
            parser_func=self._log_parser,
            path_glob_exprs=str(pathlib.Path(self.openfoam_case_dir).joinpath("log.*")),
            callback=lambda *_, **__: None,
        )

    def _post_simulation(self):
        """Upload all results found in the Openfoam case directory."""
        reg_exp = re.compile(r"([\d\.]+)")
        result_dirs = [
            dir.name
            for dir in pathlib.Path(self.openfoam_case_dir).iterdir()
            if reg_exp.match(dir.name)
        ]
        self._save_directory(result_dirs, "results.zip", "output")

        super()._post_simulation()

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

        super().launch()
