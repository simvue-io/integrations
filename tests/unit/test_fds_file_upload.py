from simvue_integrations.connectors.fds import FDSRun
import pathlib
from unittest.mock import patch
import tempfile
import uuid
import simvue
import filecmp

def mock_moose_process(self, *_, **__):
    # No need to do anything this time, just set termination trigger
    self._trigger.set()
    return True
    
@patch.object(FDSRun, 'add_process', mock_moose_process)
def test_fds_file_upload(folder_setup):    
    name = 'test_fds_file_upload-%s' % str(uuid.uuid4())
    temp_dir = tempfile.TemporaryDirectory(prefix="moose_test")
    with FDSRun() as run:
        run.init(name=name, folder=folder_setup)
        run_id = run.id
        run.launch(
            fds_input_file_path = pathlib.Path(__file__).parent.joinpath("example_data", "fds_input.fds"),
            workdir_path = pathlib.Path(__file__).parent.joinpath("example_data", "fds_outputs")
        )
        
        client = simvue.Client()
        
        # Retrieve all outputs from server and check all files exist and are the same
        client.get_artifacts_as_files(run_id, "output", temp_dir.name)
        comparison = filecmp.dircmp(pathlib.Path(__file__).parent.joinpath("example_data", "fds_outputs"), pathlib.Path(temp_dir.name))
        assert not (comparison.diff_files or comparison.left_only or comparison.right_only)