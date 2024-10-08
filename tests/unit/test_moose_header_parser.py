from simvue_integrations.connectors.moose import MooseRun
import pathlib

def test_moose_header_parser():
    with MooseRun() as run:
        header_path = pathlib.Path(__file__).parent.joinpath("example_data/moose_header.txt")
        meta, data = run._moose_header_parser(input_file=header_path)
        print(data)
        
        # Check that keys and values parsed correctly
        assert data.get("num_processors") == '1'
        
        # Check that entries with no values are not added
        assert data.get("libmesh_version") == None
        assert data.get("mesh") == None
        
        
        