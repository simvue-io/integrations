# Simvue Integrations

<br/>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://github.com/simvue-io/.github/blob/5eb8cfd2edd3269259eccd508029f269d993282f/simvue-white.png" />
    <source media="(prefers-color-scheme: light)" srcset="https://github.com/simvue-io/.github/blob/5eb8cfd2edd3269259eccd508029f269d993282f/simvue-black.png" />
    <img alt="Simvue" src="https://github.com/simvue-io/.github/blob/5eb8cfd2edd3269259eccd508029f269d993282f/simvue-black.png" width="500">
  </picture>
</p>

<p align="center">
Allow easy connection between Simvue and common simulation software packages, allowing for easy tracking and monitoring of simulations in real time.
</p>

<div align="center">
<a href="https://github.com/simvue-io/client/blob/main/LICENSE" target="_blank"><img src="https://img.shields.io/github/license/simvue-io/client"/></a>
<img src="https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue">
</div>

<h3 align="center">
 <a href="https://simvue.io"><b>Website</b></a>
  •
  <a href="https://docs.simvue.io"><b>Documentation</b></a>
</h3>

## Implemented Connectors
Currently, we have Connectors for the following software packages:
- [MOOSE](https://mooseframework.inl.gov/)
- [OpenFOAM](https://www.openfoam.com/)
- [Fire Dynamics Simulator](https://pages.nist.gov/fds-smv/)
- [TensorFlow](https://www.tensorflow.org/)

These each upload some common Metrics, Events and Metadata from files produced by simulations to the Simvue server, as well as uploading a full set of input files and results for further analysis later. They inherit from the `Run()` class of the Simvue Python API, allowing for detailed control over how your simulation is tracked.

## Configuration
The service URL and token can be defined as environment variables:
```sh
export SIMVUE_URL=...
export SIMVUE_TOKEN=...
```
or a file `simvue.toml` can be created containing:
```toml
[server]
url = "..."
token = "..."
```
The exact contents of both of the above options can be obtained directly by clicking the **Create new run** button on the web UI. Note that the environment variables have preference over the config file.

## Usage example
```python
from simvue_integrations.connectors.moose import MooseRun

...

if __name__ == "__main__":

    ...

    # Using a context manager means that the status will be set to completed automatically,
    # and also means that if the code exits with an exception this will be reported to Simvue
    with MooseRun() as run:

        # Specify a run name, metadata (dict), tags (list), description, folder
        run.init(
          name = 'my-moose-simulation',                                # Run name
          {'simulation_type': 'thermal', 'heat_capacity': 900},        # Metadata
          ['moose',],                                                  # Tags
          'MOOSE simulation of thermal properties of component.',      # Description
          '/component-1/thermal'                                       # Folder path
        )

        # Set folder details if necessary
        run.set_folder_details('/component-1/thermal',                 # Full path to folder
                               metadata={},                            # Metadata
                               tags=['moose'],                         # Tags
                               description='Thermal study of design.') # Description

        # Upload files specific to your simulation, eg mesh files:
        run.save_file('mesh,e', 'input')

        # Add an alert (the alert definition will be created if necessary)
        run.create_alert(name='temp-too-high',   # Name of Alert
                      source='metrics',          # Source
                      rule='is above',           # Rule
                      metric='temperature',      # Metric
                      frequency=1,               # Frequency
                      window=1,                  # Window
                      threshold=1000             # Threshold
                      notification='email',      # Notification type
                      trigger_abort=True)        # Abort simulation if triggered

        # Launch the MOOSE simulation
        run.launch(
            moose_application_path='app/moose-opt',   # Path to MOOSE application
            moose_file_path='thermal.i',              # Path to MOOSE input file
            )

```

## License

Released under the terms of the [Apache 2](https://github.com/simvue-io/client/blob/main/LICENSE) license.
