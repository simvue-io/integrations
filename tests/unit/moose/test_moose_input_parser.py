from simvue_integrations.connectors.moose import MooseRun
import uuid
import simvue
import pytest
import pathlib
testdata = [
    (
        "example_input_1",
        {
            "example_input_1.r": "${units 5 cm -> m}",
            "example_input_1.GlobalParams.initial_T": 310,
            "example_input_1.FluidProperties.fluid.type": "IdealGasFluidProperties",
            "example_input_1.Components.pipe.position": "'0 0 0'",
            "example_input_1.Postprocessors.T_inlet.boundary": "pipe:in",
        },
        {},
    ),
    (
        "example_input_2",
        {
            "example_input_2.Mesh.file": "mug.e",
            "example_input_2.Variables.diffused.order": "FIRST",
            "example_input_2.BCs.bottom.value": 1,
            "example_input_2.BCs.top.boundary": "'top'",
        },
        {
            "example_input_2.BCs.bottom.boundary": "'bottom' # This must match a named boundary in the mesh file",
            "example_input_2.BCs.bottom] # arbitrary user-chosen name.type": "Shouldn't exist",
            "example_input_2.Mesh.#file": "mug_2.e"
        },
    ),
    (
        "example_input_3",
        {
            "example_input_3.Mesh.file": "half-cone.e",
            "example_input_3.Variables.diffused.order": "FIRST",
            "example_input_3.Kernels.td.type": "TimeDerivative",
            "example_input_3.BCs.left.value": 2,
            "example_input_3.Outputs.exodus": "true",
        },
        {
            "example_input_3.Variables../diffused.order": "FIRST",
            "example_input_3.Executioner.#Preconditioned": "JFNK (default)",
        },
    ),
]


@pytest.mark.parametrize("file_name,expected_metadata,not_expected_metadata", testdata, ids=(1, 2, 3))
def test_moose_input_parser(folder_setup, file_name, expected_metadata, not_expected_metadata):   
    """
    Check information from MOOSE input file is correctly uploaded as metadata
    """ 
    with MooseRun() as run:
        run.init(name='test_moose_input_parser-%s' % str(uuid.uuid4()), folder=folder_setup)
        run_id = run.id
        run._moose_input_parser(pathlib.Path(__file__).parent.joinpath("example_data", f"{file_name}.i"))

        
        client = simvue.Client()
        metadata = client.get_run(run_id)['metadata']
        # Check that keys and values parsed correctly
        for key, value in expected_metadata.items():
            assert metadata.get(key) == value
    
        for key, value in not_expected_metadata.items():
            assert metadata.get(key) != value
            
        assert run._output_dir_path == "results"
        assert run._results_prefix == file_name
        
        if file_name != "example_input_2":
            assert run._dt == 0.1
        
        