import pathlib
from simvue_integrations.connectors.fds import FDSRun

def fds_minimal_example() -> None:
    current_dir = pathlib.Path(__file__).parent
    input_file = current_dir.joinpath("activate_vents.fds")

    with FDSRun() as run:
        run.init("fds_simulation_vents")
        run.launch(
            fds_input_file_path = f"{input_file}",
            workdir_path = f"{current_dir}"
        )

if __name__ in "__main__":
    fds_minimal_example()

