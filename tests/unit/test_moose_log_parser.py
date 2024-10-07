from simvue_integrations.connectors.moose import MooseRun
import simvue
import pytest
import uuid
import pathlib
def test_moose_header_parser():
    
    name = 'test_moose_header_parser-%s' % str(uuid.uuid4())
    folder = '/test-%s' % str(uuid.uuid4())
    with MooseRun() as run:
        run.init(name=name, folder=folder)
        run_id = run.id
        header_path = pathlib.Path(__file__).parent.joinpath("example_data/moose_header.txt")
        run._moose_header_parser(input_file=header_path)
        
    client = simvue.Client()
    run_data = client.get_run(run_id)
    print(run_data)
    import pdb; pdb.set_trace()
    client.delete_folder(folder_path=folder, remove_runs=True)
    
    
        
        
        