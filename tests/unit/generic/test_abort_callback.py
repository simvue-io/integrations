import time
import threading
import uuid
from unittest.mock import patch
from simvue_integrations.connectors.generic import WrappedRun
import simvue

def mock_aborted_process(self, *_, **__):
    """
    Mock a long running process which is aborted by the server
    """    
    def abort():
        """
        Instead of making an API call to the server, just sleep for 1s and return True to indicate an abort has been triggered
        """
        time.sleep(1)
        return True
    self._simvue.get_abort_status = abort
    
    def aborted_process():
        """
        Long running process which should be interrupted at the next heartbeat
        """
        self._heartbeat_interval = 2
        time.sleep(10)
        
    thread = threading.Thread(target=aborted_process)
    thread.start()
    
@patch.object(WrappedRun, '_during_simulation', mock_aborted_process)    
def test_custom_abort_callback(folder_setup):
    
    def custom_callback(self):
        self.update_metadata({"callback_triggered": True})
    
    with WrappedRun(abort_callback=custom_callback) as run:
        run.init('test_custom_abort_callback-%s' % str(uuid.uuid4()), folder=folder_setup)
        run_id = run.id
        run.launch()
                
    client = simvue.Client()
    # Check that run was aborted correctly, and did not exist for longer than 10s
    run_data = client.get_run(run_id)
    runtime = time.strptime(run_data["runtime"], '%H:%M:%S.%f')
    assert runtime.tm_sec < 10
    assert run_data["metadata"].get("callback_triggered") == True