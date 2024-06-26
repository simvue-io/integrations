import simvue
import typing
import pydantic
import multiparser.parsing.file as mp_file_parser
import multiparser.parsing.tail as mp_tail_parser
import os
import typing
import re
from simvue_integrations.wrappers.generic import WrappedRun

class OpenfoamRun(WrappedRun):
    @mp_tail_parser.log_parser
    def _log_parser(self, file_content: str, **__) -> tuple[dict[str,typing.Any], dict[str, typing.Any]]:
        
        exp1: re.Pattern[str] = re.compile(
            "^(.+):  Solving for (.+), Initial residual = (.+), Final residual = (.+), No Iterations (.+)$"
        )
        exp2: re.Pattern[str] = re.compile("^ExecutionTime = ([0-9.]+) s")
        metrics = {}
        header_metadata = {}
        title = False
        header = False
        solver_info = False

        for line in file_content.splitlines():
            # Determine where we are in the file
            if line.startswith('/*-'):
                self.log_event("Starting new execution...")
                title = True
                header = False
                solver_info = False
            if line.startswith('\*-'):
                title = False
                header = True
                solver_info = False
                continue
            elif line.startswith('// *'):
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
                key = key.strip().replace(" ","_").replace("/", "-").lower()
                value = value.strip()
                # If the line corresponds to the 'exec' parameter, store this as an event instead of a piece of metadata
                # since we will be storing data from multiple log files which are executing different things
                if key == 'exec':
                    current_process = value
                else:
                    header_metadata[key] = value

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
        super().pre_simulation()

        self.metadata_uploaded = False

        # Save the files in the System and Constants directories
        for location in ('system', 'constants'):
            if os.path.exists(os.path.join(self.openfoam_case_dir, location)):
                for dirname, _, filenames in os.walk(os.path.join(self.openfoam_case_dir, location)):
                    for filename in filenames:
                        if os.path.isfile(os.path.join(dirname,filename)):
                            self.save_file(os.path.join(dirname,filename), "input", name=f"{location}/{filename}")
            
        # TODO: Any alerts I should define?

        # Add the Openfoam simulation as a process
        self.add_process(
            identifier="openfoam_simulation",
            executable="/bin/sh",
            script=str(os.path.join(self.openfoam_case_dir, "Allrun")),
#            completion_trigger=self._trigger, # TODO: Why does this abort immediately?
            **self.openfoam_env_vars
        )
    
    def during_simulation(self):
        # Track all log files
            self.file_monitor.tail(
                parser_func=self._log_parser,
                path_glob_exprs=[os.path.join(self.openfoam_case_dir, "log.*")],
            )

    def post_simulation(self):
        # TODO: What outputs do I need to store?
        pass
                        
    @pydantic.validate_call
    def launch(
        self, 
        openfoam_case_dir: pydantic.DirectoryPath,
        openfoam_env_vars: typing.Optional[typing.Dict[str, typing.Any]] = None
        ):
        self.openfoam_case_dir = openfoam_case_dir
        self.openfoam_env_vars = openfoam_env_vars or {}

        super().launch()