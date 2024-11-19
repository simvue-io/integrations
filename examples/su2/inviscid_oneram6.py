import requests
import os
import tempfile

from simvue_integrations.connectors.su2 import SU2Run

with tempfile.TemporaryDirectory() as tempd:
    config_url = (
        "https://raw.githubusercontent.com/su2code/Tutorials/master/compressible_flow/Inviscid_ONERAM6/inv_ONERAM6.cfg"
    )

    mesh_url = (
        "https://raw.githubusercontent.com/su2code/Tutorials/master/compressible_flow/Inviscid_ONERAM6/mesh_ONERAM6_inv_ffd.su2"
    )

    config_filename: str = (
        os.path.basename(config_url)
    )
    mesh_filename: str = os.path.basename(mesh_url)

    for url, file_name in zip((config_url, mesh_url), (config_filename, mesh_filename)):

        req_response = requests.get(url)

        if req_response.status_code != 200:
            raise RuntimeError(f"Failed to retrieve file '{url}'")

        with open(os.path.join(tempd, file_name), "wb") as out_f:
            out_f.write(req_response.content)

    with SU2Run() as run:
        run.init(name="su2_inviscid_oneram6") 
        run.launch(
            configuration_file=os.path.join(tempd, config_filename),
            mesh_file=os.path.join(tempd, mesh_filename),
            workdir_path=tempd,
            su2_binary_dir=os.environ.get("SU2_DIR")
        )
