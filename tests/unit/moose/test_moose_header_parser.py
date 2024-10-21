from simvue_integrations.connectors.moose import MooseRun
import pathlib
import shutil
from unittest.mock import patch
import tempfile
import time
import threading
import uuid
import simvue
def mock_moose_process(self, *_, **__):
    """
    Mock process which creates the header of the MOOSE log (all at once, not line by line)
    """
    def create_header(self):
        shutil.copy(pathlib.Path(__file__).parent.joinpath("example_data", "moose_header.txt"), pathlib.Path(self.output_dir_path).joinpath(f"{self.results_prefix}.txt"))
        time.sleep(1)
        self._trigger.set()
    thread = threading.Thread(target=create_header, args=(self,))
    thread.start()
    
@patch.object(MooseRun, 'add_process', mock_moose_process)
def test_moose_header_parser(folder_setup):   
    """
    Check information from header of MOOSE log is correctly uploaded as metadata
    """ 
    name = 'test_moose_header_parser-%s' % str(uuid.uuid4())
    temp_dir = tempfile.TemporaryDirectory(prefix="moose_test")
    with MooseRun() as run:
        run.init(name=name, folder=folder_setup)
        run_id = run.id
        run.launch(
            moose_application_path=pathlib.Path(__file__),
            moose_file_path=pathlib.Path(__file__),
            output_dir_path=temp_dir.name,
            results_prefix="moose_test",
        )
        
        client = simvue.Client()
        metadata = client.get_run(run_id)['metadata']
        # Check that keys and values parsed correctly
        assert metadata.get("num_processors") == 1
        assert metadata.get("moose_preconditioner") == 'SMP (auto)'
        
        # Check that entries with no values are not added
        assert metadata.get("libmesh_version") == None
        assert metadata.get("mesh") == None
        
        
        