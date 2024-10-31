from examples.openfoam.openfoam_example import openfoam_example
import pytest
import pathlib
import tempfile
import simvue

def test_openfoam_connector(folder_setup):

    run_id = openfoam_example(folder_setup)
    
    client = simvue.Client()
    run_data = client.get_run(run_id)
    events = [event["message"] for event in client.get_events(run_id)]
    
    # Check run description and tags from init have been added
    assert run_data["description"] == "An example of using the OpenfoamRun Connector to track an OpenFOAM simulation."
    assert run_data["tags"] == ["openfoam", "airfoil"]
    
    # Check alert has been added
    assert "ux_residuals_too_high" in [alert["alert"]["name"] for alert in run_data["alerts"]]
    
    # Check metadata from Openfoam log header has been uploaded
    assert run_data["metadata"]["openfoam.nprocs"] == 1
    
    # Check events uploaded from log
    assert "[simpleFoam]: Create mesh for time = 0" in events
    
    # Check metrics uploaded for residuals
    assert run_data["metrics"]["residuals.final.Ux"]["count"] > 0
    
    temp_dir = tempfile.TemporaryDirectory()
    
    # Check input files uploaded as zip
    client.get_artifacts_as_files(run_id, "input", temp_dir.name)
    assert pathlib.Path(temp_dir.name).joinpath("inputs.zip").exists()
    
    # Check results uploaded as zip
    client.get_artifacts_as_files(run_id, "output", temp_dir.name)
    assert pathlib.Path(temp_dir.name).joinpath("results.zip").exists()
    
     
    
    
    