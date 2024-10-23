from examples.fds.minimal_fds import fds_example
import pathlib
import tempfile
import simvue

def test_fds_connector(check_fds_setup, folder_setup):
    assert check_fds_setup
    
    run_id = fds_example(folder_setup)
    
    client = simvue.Client()
    run_data = client.get_run(run_id)
    events = [event["message"] for event in client.get_events(run_id)]
    
    # Check run description and tags from init have been added
    assert run_data["description"] == "An example of using the FDSRun Connector to track an FDS simulation."
    assert run_data["tags"] == ['fds', 'vents']
    
    # Check alert has been added
    assert "visibility_below_three_metres" in [alert["alert"]["name"] for alert in run_data["alerts"]]
    
    # Check metadata from header
    assert run_data["metadata"]["fds.mpi_processes"] == 1
    
    # Check metadata from input file
    assert run_data["metadata"]["_grp_devc_1.id"] == "flow_volume_supply"
    
    # Check events from log
    assert "Time Step: 1, Simulation Time: 0.092 s" in events
    
    # Check events from DEVC/CTRL log
    assert "DEVC 'timer' has been set to 'True' at time 2.00296E+00s, when it reached a value of 2.00296E+00s." in events
        
    # Check metrics from HRR file
    assert run_data["metrics"]["HRR"]["count"] > 0
    
    # Check metrics from DEVC file
    assert run_data["metrics"]["flow_volume_supply"]["count"] > 0

    temp_dir = tempfile.TemporaryDirectory()
    
    # Check input file uploaded as input
    client.get_artifacts_as_files(run_id, "input", temp_dir.name)
    assert pathlib.Path(temp_dir.name).joinpath("activate_vents.fds").exists()
    
    # Check results uploaded as output
    client.get_artifacts_as_files(run_id, "output", temp_dir.name)
    assert pathlib.Path(temp_dir.name).joinpath("supply_exhaust_vents.smv").exists()