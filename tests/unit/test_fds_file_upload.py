from simvue_integrations.connectors.fds import FDSRun
import pathlib
from unittest.mock import patch
import tempfile
import uuid
import simvue
import filecmp
import shutil

def mock_fds_process(self, *_, **__):
    # copy all files from example_data to temp dir
    shutil.copytree(pathlib.Path(__file__).joinpath("example_data", "fds_outputs"), self.workdir_path)    
    self._trigger.set()
    return True
    
@patch.object(FDSRun, 'add_process', mock_fds_process)
def test_fds_file_upload(folder_setup):    
    name = 'test_fds_file_upload-%s' % str(uuid.uuid4())
    temp_dir = tempfile.TemporaryDirectory(prefix="moose_test")
    with FDSRun() as run:
        run.init(name=name, folder=folder_setup)
        run_id = run.id
        run.launch(
            fds_input_file_path = pathlib.Path(__file__).parent.joinpath("example_data", "fds_input.fds"),
            workdir_path = temp_dir.name
        )
        
        client = simvue.Client()
        
        # Retrieve all outputs from server and check all files exist and are the same
        retrieved_dir = pathlib.Path(temp_dir.name).joinpath("retrieved_results").mkdir()
        client.get_artifacts_as_files(run_id, "output", str(retrieved_dir))
        comparison = filecmp.dircmp(pathlib.Path(__file__).parent.joinpath("example_data", "fds_outputs"), retrieved_dir)
        assert not (comparison.diff_files or comparison.left_only or comparison.right_only)