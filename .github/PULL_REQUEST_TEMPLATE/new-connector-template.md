# Pull Request Template for New Connector to Non-Python Software

## Description of Connector
[Describe what this Connector does - eg what values from which output files does it track, what does it upload to Simvue, why is it useful?]

## Software Details
**Target Software**: [Enter name of software being tracked by this connector here]
**Description of Software**: [Briefly describe what the software does]
**Link to Software**: [Link to installation instructions or documentation for software]

## Testing Performed
**Tested Version(s)**: [Versions of the software which the connector has been tested against - comma separated]
**Tested Operating Systems**: [Names of operating systems which this has been tested against]
**Tested Python Versions**: [The python versions which this connector has been tested against]
**Tested Simvue Python API Versions**: [Versions of the Python API which this connector has been tested against]

## Documentation
**Link to Documentation PR**: [Provide a link to a Pull Request in the Documentation repo, where the `Integrations` and `Examples` pages have been updated to include your Connector]
**Link to Docker Container**: [Provide a link to a Docker container which contains the simulation software being tracked and some examples of your Connector in use]

## Checklist
- [ ] Code corresponds to the guidelines set out in the Contributing.md document
- [ ] Connector inherits from the generic `WrappedRun` class
- [ ] Unit tests have been added which check all functionality of the Connector, using Mock functions to replicate the simulation software
- [ ] All unit tests run and pass locally
- [ ] Integration tests have been added into the CI and are passing
- [ ] Code passes all pre-commit hooks
- [ ] The `Integrations` and `Examples` pages of the documentation have been updated to include information about your Connector, following the existing format
- [ ] A Docker image has been provided and pushed to the github Registry, which contains the simulation software being tracked, and examples of your Connector
- [ ] Example scripts of the connector in use have been provided

