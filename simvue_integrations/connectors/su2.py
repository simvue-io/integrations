"""
SU2 Simvue run
==============

Contains a class for creating an SU2 based simulation under Simvue.

"""
__author__ = "Kristian Zarebski <kristian.zarebski@ukea.uk>"
__date__ = "2024-09-23"

import typing
import os
import pathlib
import pydantic
from simvue_integrations.connectors.generic import WrappedRun

import multiparser.parsing.tail as mp_tail_parse
import multiparser.parsing.file as mp_file_parse

OUTPUT_FILES: list[str] = ["flow.vtk", "surface_flow.vtk", "restart_flow.dat"]
METADATA_ATTRS: list[str] = [
    "SOLVER",
    "MATH_PROBLEM",
    "MACH_NUMBER",
    "AOA",
    "SIDESLIP_ANGLE",
    "FREESTREAM_PRESSURE",
    "FREESTREAM_TEMPERATURE",
]


class SU2Run(WrappedRun):
    """SU2 Simvue tracked Simulation

    This is a wrapper to the Simvue Run class for initialising and
    executing simulations using the SU2 framework.
    """
    configuration_file: typing.Optional[pathlib.Path] = None
    mesh_file: typing.Optional[pathlib.Path] = None
    workdir_path: pathlib.Path = pathlib.Path.cwd()
    output_files: typing.Optional[list[pathlib.Path]] = None
    binary_dir: typing.Optional[pathlib.Path] = None

    def pre_simulation(self) -> None:
        """Define and execute the SU2 simulation process"""
        super().pre_simulation()
        self.log_event("Starting SU2 simulation")
        self.save_file(self.mesh_file, "input")

        environment: dict[str, str] = os.environ.copy()

        if self.binary_dir:
            environment["PATH"] = (
                f"{self.binary_dir.absolute()}:{os.environ['PATH']}"
            )
            pypath = os.environ.get("PYTHONPATH")
            environment["PYTHONPATH"] = (
                f"{os.path.abspath(self.binary_dir)}{f':{pypath}' if pypath else ''}"
            )

        self.add_process(
            "su2_simulation",
            executable="SU2_CFD",
            script=self.configuration_file,
            env=environment,
            cwd=self.workdir_path,
            completion_trigger=self._trigger
        )

    @pydantic.validate_call
    def launch(
        self,
        configuration_file: pydantic.FilePath,
        mesh_file: pydantic.FilePath,
        su2_binary_dir: typing.Optional[pydantic.DirectoryPath],
        workdir_path: typing.Optional[pydantic.DirectoryPath] = None,
        upload_files: typing.Optional[
            list[typing.Literal["flow.vtk", "surface_flow.vtk", "restart_flow.dat"]]
        ] = None,
    ) -> None:
        """Command to launch the SU2 simulation and track it with Simvue

        Parameters
        ----------
        configuration_file: str | pathlib.Path
            Path to the SU2 simulation configuration file
        mesh_file: str | pathlib.Path
            Path to the SU2 simulation mesh file
        su2_binary_dir: str | pathlib.Path | None
            Specify the location of the SU binaries, only required if
            PATH and PYTHONPATH environment variables have not been updated
        workdir_path: str | pathlib.Path, optional
            Specify the directory within which to run the simulation
        upload_files: list[str] | None, optional
            List of output files to upload, if None, upload all
        """
        self.configuration_file = configuration_file
        self.mesh_file = mesh_file
        self.workdir_path = workdir_path or self.workdir_path
        upload_files = upload_files if upload_files is not None else OUTPUT_FILES
        self.output_files = [
            self.workdir_path.joinpath(out)
            for out in upload_files
        ] if upload_files else None
        self.binary_dir = su2_binary_dir

        if self.workdir_path:
            self.workdir_path.mkdir(exist_ok=True, parents=True)

        for file in self.output_files or []:
            file.unlink(missing_ok=True)

        super().launch()

    def during_simulation(self) -> None:
        """Define tracked and tailed files for monitoring with Multiparser"""
        self.file_monitor.track(
            path_glob_exprs=[f"{self.configuration_file}"],
            parser_func=self.metadata_parser,
            callback=lambda meta, *_: self.update_metadata(meta)
        )
        self.file_monitor.tail(
            path_glob_exprs=[f"{self.workdir_path.joinpath('history.csv')}"],
            parser_func=mp_tail_parse.record_csv,
            callback=lambda metrics, *_: self.log_metrics(
                {
                    key.replace("[", "_").replace("]", ""): value
                    for key, value in metrics.items()
                }
            ),
        )

    def post_simulation(self) -> None:
        """Uploads output files to Simvue storage"""
        for output_file in self.output_files or []:
            self.save_file(f"{output_file}", "output")

    @mp_file_parse.file_parser
    def metadata_parser(
        self, input_file: str, **_
    ) -> tuple[dict[str, typing.Any], dict[str, typing.Any]]:
        """Define parser used to record simulation metadata"""
        metadata = {}
        with open(input_file) as in_csv:
            file_content = in_csv.read()

        for line in file_content.splitlines():
            for attr in METADATA_ATTRS:
                if line.startswith(attr):
                    metadata[f"su2.{attr.lower()}"] = line.split("%s= " % attr)[1].strip()
        return {}, metadata

