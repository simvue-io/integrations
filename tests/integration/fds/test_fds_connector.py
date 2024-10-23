from examples.fds.minimal_fds import fds_example
import pytest
import simvue

def test_fds_connector(check_fds_setup, folder_setup):
    assert check_fds_setup
    
    run_id = fds_example(folder_setup)
    
    client = simvue.Client()
    run_data = client.get_run(run_id)
    
    # Check run description and tags from init have been added
    
    # Check alert has been added
    
    # Check metadata from header
    
    # Check metadata from input file
    
    # Check events from log
    
    # Check events and metadata from CTRL log
    
    # Check metrics from HRR file
    
    # Check metrics from DEVC file
    