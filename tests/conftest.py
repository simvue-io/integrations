import pytest
import simvue
import uuid
@pytest.fixture(scope='session', autouse=True)
def folder_setup():
    # Will be executed before the first test
    folder  = '/tests-connectors-%s' % str(uuid.uuid4())
    yield folder
    # Will be executed after the last test
    client = simvue.Client()
    client.delete_folder(folder, remove_runs=True)