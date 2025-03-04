from simvue_integrations.connectors.openfoam import OpenfoamRun
import simvue
import threading
import multiprocessing
import time
import contextlib
import tempfile
from unittest.mock import patch
import uuid
import pathlib

def mock_openfoam_process(self, *_, **__):
    """
    Mock process for writing Openfoam log.
    """
    def write_to_log():
        # Openfoam writes log files in large chunks of lines
        # Header, pre run info, and some metrics are written initially
        # Then more chunks of metrics are written over time
        with pathlib.Path(self.openfoam_case_dir).joinpath("log.openfoam").open(mode="w") as temp_logfile:
            with pathlib.Path(__file__).parent.joinpath("example_data", "openfoam_log_initial.txt").open("r") as log_file_initial:
                for line in log_file_initial:
                    temp_logfile.write(line)
            temp_logfile.flush()
            time.sleep(1)
            with pathlib.Path(__file__).parent.joinpath("example_data", "openfoam_log_lines.txt").open("r") as log_file_next:
                for line in log_file_next:
                    temp_logfile.write(line)
            temp_logfile.flush()
            time.sleep(1)
        self._trigger.set()
        return
    thread = threading.Thread(target=write_to_log)
    thread.start()
    
@patch.object(OpenfoamRun, 'add_process', mock_openfoam_process)
def test_openfoam_log_parser(folder_setup):
    """
    Check that relevant information is uploaded from the Openfoam log,
    including metadata from header, and residuals as metrics.
    """
    name = 'test_openfoam_parser-%s' % str(uuid.uuid4())
    temp_dir = tempfile.TemporaryDirectory(prefix="openfoam_test")
    with OpenfoamRun() as run:
        run.config(disable_resources_metrics=True)
        run.init(name=name, folder=folder_setup)
        run_id = run.id
        run.launch(
            openfoam_case_dir = temp_dir.name,
        )
           
    client = simvue.Client()
    # Check metadata from header is uploaded correctly
    run_data = client.get_run(run_id)
    assert run_data.metadata["openfoam"]["build"] == "10-e450dce21ea5"
    assert run_data.metadata["openfoam"]["allowsystemoperations"] == "Allowing user-supplied system call operations"
    # Check that exec param is not uploaded as metadata - this is used in the events log
    assert not run_data.metadata["openfoam"].get("exec")
    
    # Check pre-simulation messages correctly extracted from log and added as events
    events = client.get_events(run_id)
    assert events[1]["message"] == "[pimpleFoam]: Create time"
    
    # Check that residuals are correctly uploaded as metrics
    # Check that 12 metrics have been created (initial and final for the 6 variables being solved in the log)
    metrics_names = client.get_metrics_names(run_id)
    assert sum(1 for i in metrics_names) == 12
    
    # Check residual times and values match those in log file
    sample_metric = client.get_metric_values(metric_names=["residuals.initial.p"], xaxis="time", output_format="dataframe", run_ids=[run_id])
    times = [round(num, 6) for num in list(sample_metric.index.levels[0])]
    assert times == [0.063383, 0.081839, 0.100079, 0.117121, 0.134495, 0.151338, 0.172352, 0.190811, 0.207135, 0.224044]
    metric_values = sample_metric['residuals.initial.p'].tolist()
    assert metric_values == [0.0132272, 0.122032, 0.123376, 0.0504458, 0.0151648, 0.00860574, 0.00697087, 0.00660373, 0.00610801, 0.00542434]
        