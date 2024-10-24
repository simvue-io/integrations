from examples.moose.moose_example import moose_example
import pytest
import subprocess
import pathlib
import tempfile
import simvue

def test_moose_connector(folder_setup):
    try:
        subprocess.run("/opt/moose/bin/moose-opt")
    except FileNotFoundError:
        pytest.skip("You are attempting to run MOOSE Integration Tests without having MOOSE installed.")
    
    run_id = moose_example("/opt/moose/bin/moose-opt", folder_setup)
    
    client = simvue.Client()
    run_data = client.get_run(run_id)
    assert True