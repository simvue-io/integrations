from simvue_integrations.connectors.openfoam import OpenfoamRun
import simvue
from simvue.api.objects import Run
import tempfile
from unittest.mock import patch
import uuid
import pathlib
import filecmp
import zipfile
import time
import threading

def mock_openfoam_process(self, *_, **__):
    # No need to do anything this time, just set termination trigger
    self._trigger.set()
    return True
    
@patch.object(OpenfoamRun, 'add_process', mock_openfoam_process)
def test_openfoam_file_upload(folder_setup):    
    """
    Check that all files in output case directory are uploaded to Simvue,
    as individual files when upload_as_zip is False.
    """
    name = 'test_openfoam_file_upload-%s' % str(uuid.uuid4())
    temp_dir = tempfile.TemporaryDirectory(prefix="openfoam_test")
    with OpenfoamRun() as run:
        run.config(disable_resources_metrics=True)
        run.init(name=name, folder=folder_setup)
        run_id = run.id
        run.launch(
            openfoam_case_dir = pathlib.Path(__file__).parent.joinpath("example_data", "openfoam_case"),
            upload_as_zip=False,
            
        )
           
    client = simvue.Client()
    # Pull artifacts, check system, constants, initial conditions, results have been uploaded (not as zip files)
    temp_dir = tempfile.TemporaryDirectory(prefix="openfoam_test")
    temp_dir_path = pathlib.Path(temp_dir.name)
    client.get_artifacts_as_files(run_id, "input", temp_dir.name)
    client.get_artifacts_as_files(run_id, "output", temp_dir.name)
    
    # Compare each directory individually, because dircmp is not recursive
    for temp_subdir_path in temp_dir_path.rglob("./"):
        example_path = pathlib.Path(__file__).parent.joinpath("example_data", "openfoam_case")
        if temp_subdir_path != temp_dir_path:
            example_path = example_path.joinpath(temp_subdir_path.parts[-1])
        comparison = filecmp.dircmp(example_path, temp_subdir_path)
        # Check all files present and identical
        assert not (comparison.diff_files or comparison.left_only or comparison.right_only)
    
    
@patch.object(OpenfoamRun, 'add_process', mock_openfoam_process)
def test_openfoam_file_upload_zipped(folder_setup):    
    """
    Check that all files from case directory are uploaded to artifacts,
    split into two archives - one for inputs, one for results.
    """
    name = 'test_openfoam_file_upload-%s' % str(uuid.uuid4())
    temp_dir = tempfile.TemporaryDirectory(prefix="openfoam_test")
    with OpenfoamRun() as run:
        run.config(disable_resources_metrics=True)
        run.init(name=name, folder=folder_setup)
        run_id = run.id
        run.launch(
            openfoam_case_dir = pathlib.Path(__file__).parent.joinpath("example_data", "openfoam_case"),
            upload_as_zip=True,
            
        )
           
    client = simvue.Client()
    # Pull artifacts, check inputs and outputs uploaded as zip files
    temp_dir = tempfile.TemporaryDirectory(prefix="openfoam_test")
    temp_dir_path = pathlib.Path(temp_dir.name)
    example_dir_path = pathlib.Path(__file__).parent.joinpath("example_data", "openfoam_case")
    client.get_artifacts_as_files(run_id, "input", temp_dir.name)
    client.get_artifacts_as_files(run_id, "output", temp_dir.name)
    
    for file in ["inputs", "results"]:
        file_path = pathlib.Path(temp_dir.name).joinpath(f"{file}.zip")
        assert file_path.is_file()
        # Extract files from zip file to directory to check contents
        with zipfile.ZipFile(file_path) as zip_file:
            zip_file.extractall(pathlib.Path(temp_dir.name).joinpath(file))
    
    dirs_to_compare = {
        example_dir_path.joinpath("system"): temp_dir_path.joinpath("inputs", "system"),
        example_dir_path.joinpath("constant"): temp_dir_path.joinpath("inputs", "constant"),
        example_dir_path.joinpath("0"): temp_dir_path.joinpath("inputs", "0"),
        example_dir_path.joinpath("0"): temp_dir_path.joinpath("results", "0"),
        example_dir_path.joinpath("0.003"): temp_dir_path.joinpath("results", "0.003"),
    }
    # Check file contents are the same
    for example_path, temp_path in dirs_to_compare.items():
        comparison = filecmp.dircmp(example_path, temp_path)
        assert not (comparison.diff_files or comparison.left_only or comparison.right_only)
        
        
def mock_aborted_openfoam_process(self, *_, **__):
    """
    Mock a long running OpenFOAM process which is aborted by the server
    """
    def aborted_process():
        """
        Long running process which should be interrupted at the next heartbeat
        """
        self._heartbeat_interval = 2
        time_elapsed = 0
        while time_elapsed < 30:
            if self._alert_raised_trigger():
                break
            time.sleep(1)
            time_elapsed += 1
        self._trigger.set()
        
    thread = threading.Thread(target=aborted_process)
    thread.start()
    
def abort():
    """
    Instead of making an API call to the server, just sleep for 1s and return True to indicate an abort has been triggered
    """
    time.sleep(2)
    return True
    
@patch.object(OpenfoamRun, 'add_process', mock_aborted_openfoam_process)
@patch.object(Run, 'abort_trigger', abort)    
def test_openfoam_file_upload_after_abort(folder_setup):
    """
    Check that outputs are uploaded if the simulation is aborted early by Simvue
    """
    name = 'test_openfoam_file_upload_after_abort-%s' % str(uuid.uuid4())
    temp_dir = tempfile.TemporaryDirectory(prefix="openfoam_test")
    with OpenfoamRun() as run:
        run.config(disable_resources_metrics=True)
        run.init(name=name, folder=folder_setup)
        run._heartbeat_interval = 2
        run._sv_obj.get_abort_status = abort
        run_id = run.id
        run.launch(
            openfoam_case_dir = pathlib.Path(__file__).parent.joinpath("example_data", "openfoam_case"),
            upload_as_zip=False,
            
        )
           
    client = simvue.Client()
    
    # Check that run was aborted correctly, and did not exist for longer than 10s
    runtime = client.get_run(run_id).runtime
    assert runtime.tm_sec < 30
    
    # Pull artifacts, check system, constants, initial conditions, results have been uploaded (not as zip files)
    temp_dir = tempfile.TemporaryDirectory(prefix="openfoam_test")
    temp_dir_path = pathlib.Path(temp_dir.name)
    client.get_artifacts_as_files(run_id, "input", temp_dir.name)
    client.get_artifacts_as_files(run_id, "output", temp_dir.name)
    
    # Compare each directory individually, because dircmp is not recursive
    for temp_subdir_path in temp_dir_path.rglob("./"):
        example_path = pathlib.Path(__file__).parent.joinpath("example_data", "openfoam_case")
        if temp_subdir_path != temp_dir_path:
            example_path = example_path.joinpath(temp_subdir_path.parts[-1])
        comparison = filecmp.dircmp(example_path, temp_subdir_path)
        # Check all files present and identical
        assert not (comparison.diff_files or comparison.left_only or comparison.right_only)
