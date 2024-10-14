from simvue_integrations.connectors.moose import MooseRun
import simvue
import threading
import multiprocessing
import time
import contextlib
import tempfile
from unittest.mock import patch
import uuid
import pathlib

def mock_moose_process(self, *_, **__):
    temp_logfile = tempfile.NamedTemporaryFile(mode="w",prefix="moose_test_", suffix=".csv", buffering=1)
    self.results_prefix = temp_logfile.name.split(".")[0]
    def write_to_csv(temp_logfile=temp_logfile):
        log_file = pathlib.Path(__file__).parent.joinpath("example_data/moose_temps_avgs.csv").open("r")
        for line in log_file:
            print(line)
            temp_logfile.write(line)
            time.sleep(0.1)
        temp_logfile.flush()
        time.sleep(1)
        temp_logfile.close()
        self._trigger.set()
        return
    thread = threading.Thread(target=write_to_csv)
    thread.start()
    
@patch.object(MooseRun, 'add_process', mock_moose_process)
def test_moose_header_parser(folder_setup):    
    name = 'test_moose_header_parser-%s' % str(uuid.uuid4())
    with MooseRun() as run:
        run.init(name=name, folder=folder_setup)
        run_id = run.id
        run.launch(
            moose_application_path=pathlib.Path(__file__),
            moose_file_path=pathlib.Path(__file__),
            output_dir_path=f"/tmp/",
            results_prefix="overwritten_in_mocker",
        )
           
    client = simvue.Client()
    
    # Check that 3 metrics have been created for each PostProcessor
    metrics_names = client.get_metrics_names(run_id)
    assert len(metrics_names) == 3
    
    # Get metric 'handle_temp_avg', check that time values are correct
    sample_metric = client.get_metric_values(metric_names=["handle_temp_avg"], xaxis="time", output_format="dataframe", run_ids=[run_id])
    assert list(sample_metric.index.levels[0]) == [0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0]
    
    # Check that the values are correct
    metric_values = sample_metric['handle_temp_avg'].tolist()
    metric_ints = [int(val) for val in metric_values]
    assert metric_ints == [0,227,327,388,427,452,469,480,487,491,494]     
        
        