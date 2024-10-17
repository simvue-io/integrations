from simvue_integrations.connectors.moose import MooseRun
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
    
@patch.object(MooseRun, 'add_process', mock_moose_process)
def test_moose_header_parser(folder_setup):    
    name = 'test_moose_header_parser-%s' % str(uuid.uuid4())
    temp_dir = tempfile.TemporaryDirectory(prefix="moose_test")
    with MooseRun() as run:
        run.init(name=name, folder=folder_setup)
        run_id = run.id
        run.launch(
            moose_application_path=pathlib.Path(__file__),
            moose_file_path=pathlib.Path(__file__),
            output_dir_path=str(pathlib.Path(__file__).parent.joinpath("example_data", "moose_outputs")),
            results_prefix="moose_test",
        )
        
        client = simvue.Client()
        
        # Retrieve Exodus file from server and compare with local copy
        client.get_artifacts_as_files(run_id, "output", temp_dir.name)
        filecmp.cmp(pathlib.Path(__file__).parent.joinpath("example_data", "moose_outputs", "moose_test.e"), pathlib.Path(temp_dir.name).joinpath("moose_test.e"))