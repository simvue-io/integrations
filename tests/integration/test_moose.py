from examples.moose.moose_example import moose_example
import pytest
import subprocess
import pathlib
import tempfile
import simvue

def test_moose_connector():
    try:
        subprocess.run("/opt/moose/bin/moose-opt")
    except FileNotFoundError:
        pytest.skip("You are attempting to run MOOSE Integration Tests without having MOOSE installed.")
    
    run_id = moose_example("/opt/moose/bin/moose-opt")
    
    client = simvue.Client()
    run_data = client.get_run(run_id)
    events = [event["message"] for event in client.get_events(run_id)]
    
    # Check run description and tags from init have been added
    assert run_data["description"] == "An example of using the MooseRun Connector to track a MOOSE simulation."
    assert run_data["tags"] == ['moose', 'thermal', 'diffusion']
    
    # Check alert has been added
    assert "avg_temp_above_500" in [alert["alert"]["name"] for alert in run_data["alerts"]]
    
    # Check metadata from MOOSE log header has been uploaded
    assert run_data["metadata"]["moose.executioner"] == "Transient"
    
    # Check events uploaded from log
    assert "Time Step 1, time = 2, dt = 2" in events
    
    # Check metrics uploaded from PostProcessor CSV
    assert run_data["metrics"]["average_temperature"]["last"] > 499
    
    # Check metrics uploaded from VectorPostProcessor CSV
    assert run_data["metrics"]["temperature_along_bar.T.0"]["count"] == 15
    
    temp_dir = tempfile.TemporaryDirectory()
    
    # Check input file uploaded as input
    client.get_artifacts_as_files(run_id, "input", temp_dir.name)
    assert pathlib.Path(temp_dir.name).joinpath("thermal_bar.i").exists()
    
    # Check results uploaded as output
    client.get_artifacts_as_files(run_id, "output", temp_dir.name)
    assert pathlib.Path(temp_dir.name).joinpath("simvue_thermal.e").exists()
    
     
    
    
    