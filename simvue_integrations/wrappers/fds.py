import typing
import pydantic
import glob
import os.path
import re
import os
import f90nml

import multiparser.parsing.tail as mp_tail_parser

from simvue_integrations.wrappers.generic import WrappedRun

class FDSRun(WrappedRun):

    @mp_tail_parser.log_parser
    def _log_parser(self, file_data: str, **__) -> tuple[dict[str,typing.Any], list[dict[str, typing.Any]]]:

        _out_data = []
        _out_record = {}

        for line in file_data.split("\n"):
            for pattern in self._patterns:
                match = pattern["pattern"].search(line)
                if match:
                    if pattern["name"] == "step":
                        if _out_record:
                            _out_data += [_out_record]
                        _out_record = {}
                    _out_record[pattern["name"]] = match.group(1)

            if 'DEVICE Activation Times' in line:
                self._activation_times = True
                print('DEVICE Activation Times')
            elif self._activation_times and 'Time Stepping' in line:
                self._activation_times = False
            elif self._activation_times:
                match = re.match('\s+\d+\s+([\w]+)\s+([\d\.]+)\ss.*', line)
                if match:
                    self._activation_times_data[f"{match.group(1)}_activation_time"] = float(match.group(2))

        if _out_record:
            _out_data += [_out_record]

        return {}, _out_data
    
    def _metrics_callback(self, data, meta):
        if "time" in data and "step" in data:
            mytime = data["time"]
            mystep = data["step"]
            del data["time"]
            del data["step"]
            self.log_metrics(
                data, timestamp=meta["timestamp"], time=mytime, step=mystep
            )
        elif "Time" in data:
            mytime = data["Time"]
            del data["Time"]
            self.log_metrics(data, timestamp=meta["timestamp"], time=mytime)
        else:
            self.log_metrics(data, timestamp=meta["timestamp"])

    def pre_simulation(self):
        super().pre_simulation()

        self.save_file(self.fds_input_file_path, 'input')

        self.add_process(
            "fds_simulation",
            executable="fds_unlim",
            input_file=self.fds_input_file_path,
            completion_callback=lambda *_, **__: self._trigger.set(),
            env=os.environ | {"PATH": f"{os.environ['PATH']}:{os.getcwd()}"},
            ulimit=self.ulimit,
            **self.fds_env_vars
        )
    
    def during_simulation(self):
        # Upload data from input file as metadata
        self.file_monitor.track(
            path_glob_exprs=self.fds_input_file_path,
            callback=lambda data, _: self.update_metadata({k: v for k, v in data.items() if v}),
            file_type="fortran",
            static=True,
        )
        self.file_monitor.tail(
            path_glob_exprs=f"{self._chid}.out",
            parser_func=self._log_parser,
            callback=self._metrics_callback
        )
        self.file_monitor.tail(
            path_glob_exprs=f"{self._chid}_hrr.csv",
            parser_func=mp_tail_parser.record_csv,
            parser_kwargs={"header_pattern": "Time"},
            callback=self._metrics_callback
        )
        self.file_monitor.tail(
            path_glob_exprs=f"{self._chid}_devc.csv",
            parser_func=mp_tail_parser.record_csv,
            parser_kwargs={"header_pattern": "Time"},
            callback=self._metrics_callback
        )

    def post_simulation(self):
        self.update_metadata(self._activation_times_data)

    @pydantic.validate_call
    def launch(
        self, 
        fds_input_file_path: pydantic.FilePath,
        ulimit: typing.Union[str, int] = "unlimited",
        fds_env_vars: typing.Optional[typing.Dict[str, typing.Any]] = None
        ):
        self.fds_input_file_path = fds_input_file_path
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
                "name": "min_divergence",
            },
            {
                "pattern": re.compile(
                    r"\s+Min\sdivergence:\s+([\d\.E\-\+]+)\sat\s\(\d+,\d+,\d+\)$"
                ),
                "name": "max_divergence",
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
                "pattern": re.compile(r"\s+Total\sHeat\sRelease\sRate:\s+([\d\.\-]+)\skW$"),
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

        for csv_file in glob.glob(f"{self._chid}*.csv"):
            os.remove(csv_file)

        super().launch()