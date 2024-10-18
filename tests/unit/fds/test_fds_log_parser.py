from simvue_integrations.connectors.fds import FDSRun
import simvue
import threading
import multiprocessing
import time
import contextlib
import tempfile
from unittest.mock import patch
import uuid
import pathlib

def mock_fds_process(self, *_, **__):
    temp_logfile = pathlib.Path(self.workdir_path).joinpath("fds_test.out").open(mode="w")
    def write_to_log():
        log_file = pathlib.Path(__file__).parent.joinpath("example_data", "fds_log.txt").open("r")
        line_counter = 0
        for line in log_file:
            temp_logfile.write(line)
            time.sleep(0.01)
            # FDS file writes to the file in blocks, writing all lines for a given time step at once
            # This is always 13 lines, except the first two time steps which dont report HRR and heat loss to boundary
            # Have removed those from the log file to make life easier here
            line_counter += 1
            if line_counter == 13:
                temp_logfile.flush()
                line_counter = 0
            
        temp_logfile.flush()
        time.sleep(1)
        temp_logfile.close()
        self._trigger.set()
        return
    thread = threading.Thread(target=write_to_log)
    thread.start()

@patch.object(FDSRun, 'add_process', mock_fds_process)
def test_fds_log_parser(folder_setup):    
    name = 'test_fds_log_parser-%s' % str(uuid.uuid4())
    temp_dir = tempfile.TemporaryDirectory(prefix="fds_test")
    with FDSRun() as run:
        run.init(name=name, folder=folder_setup)
        run_id = run.id
        run.launch(
            fds_input_file_path = pathlib.Path(__file__).parent.joinpath("example_data", "fds_input.fds"),
            workdir_path = temp_dir.name,
        )
           
    client = simvue.Client()
        
    # Check that 9 metrics have been created, one for each line in log per timestep
    metrics_names = client.get_metrics_names(run_id)
    assert len(metrics_names) == 9
    
    # Get all metrics from run, check last value of each matches last set of lines in file
    run_data = client.get_run(run_id)
    metrics = run_data["metrics"]
    expected_results = {
        "max_vn": 0.14,
        "max_divergence": 3.2,
        "min_divergence": -1.0,
        "max_cfl": 0.17,
        "max_pressure_error": 730,
        "total_heat_release_rate": 152.324,
        "max_velocity_error": 0.0087,
        "radiation_loss_to_boundaries": -35.118,
        "pressure_iteration": 1
    }
    for key, values in metrics.items():
        assert values["last"] == expected_results[key]
        
    # Check device activation time added as metadata
    assert run_data["metadata"].get("timer_activation_time") == 3.003