"""Generic Connector.

Generic connector class to build on top of when creating integrations for non-Python software.
"""

import multiprocessing
import typing

import click
import multiparser
import simvue

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self


class WrappedRun(simvue.Run):
    """Generic wrapper to the Run class which can be used to build Connectors to non-python applications.

    New Connectors should inherit from this class, and override the specific methods below to add functionality
    for their given application. Make sure to call the base method as well.
    """

    _terminated = False

    def __init__(
        self,
        mode: typing.Literal["online", "offline", "disabled"] = "online",
        abort_callback: typing.Optional[typing.Callable[[Self], None]] = None,
        server_token: typing.Optional[str] = None,
        server_url: typing.Optional[str] = None,
        debug: bool = False,
    ):
        """Initialize the WrappedRun instance, extending the user supplied alert abort callback.

        If `abort_callback` is provided the first argument must be this Run instance

        Parameters
        ----------
        mode : typing.Literal['online', 'offline', 'disabled'], optional
            mode of running, by default 'online':
                online - objects sent directly to Simvue server
                offline - everything is written to disk for later dispatch
                disabled - disable monitoring completelyby default "online"
        abort_callback : typing.Optional[typing.Callable[[Self], None]], optional
            callback executed when the run is aborted, by default None
        server_token : typing.Optional[str], optional
            overwrite value for server token, by default None
        server_url : typing.Optional[str], optional
            overwrite value for server URL, by default None
        debug : bool, optional
            run in debug mode, by default False

        """

        def _extended_abort_callback(self):
            """Extend the user supplied abort alert callback to allow for the soft stop of simulations."""
            if abort_callback:
                abort_callback(self)
            self._soft_abort()

        super().__init__(
            mode=mode,
            abort_callback=_extended_abort_callback,
            server_token=server_token,
            server_url=server_url,
            debug=debug,
        )

    def _soft_abort(self):
        """How to stop simluations from running safely when an abort is triggered.

        By default, kills the process associated with the simulation, then stops the file monitor using _trigger.
        The Run will then proceed to run the code in `post_simulation`, and then close as normal.
        """
        self.kill_all_processes()
        self._trigger.set()

    def _pre_simulation(self):
        """Execute after launch() is called, but before a simulation begins.

        By default, creates a termination trigger for the FileMonitor to use, and checks that a Simvue run has
        been initialised. This method should be called BEFORE the rest of your functions in the overriden method.
        """
        self._trigger = multiprocessing.Event()

        if not self._simvue:
            self._error("Run must be initialized before launching the simulation.")
            return False

        # Uses 'ignore' so that on abort, run is not closed before post_simulation is run.
        self._abort_on_alert = "ignore"

    def _during_simulation(self):
        """Execute after launch() is called and after the simulation begins, within the FileMonitor."""
        pass

    def _post_simulation(self):
        """Execute after launch() is called and after the simulation finishes.

        By default, checks whether an abort has been caused by an alert, and if so prints a message and sets
        the run to the terminated state. This method should be called AFTER the rest of your functions in the overriden method.
        """
        if self._alert_raised_trigger.is_set():
            self.log_event("Simulation aborted due to an alert being triggered.")
            self._terminated = True
            click.secho(
                "[simvue] Run was aborted.",
                fg="red" if self._term_color else None,
                bold=self._term_color,
            )
        else:
            self.log_event("Simulation Complete!")

    def __exit__(self, exc_type, value, traceback):
        """Set run status to terminated if the simulation was stopped by an alert."""
        _out = super().__exit__(exc_type, value, traceback)
        # If run was terminated, set the status to terminated at the very end so that users can continue to upload to the run as normal
        if self._terminated:
            self.set_status("terminated")
        return _out

    def launch(self):
        """Launch the simulation and the monitoring.

        By default calls the three methods above, and sets up a FileMonitor for tracking files.
        """
        self._pre_simulation()

        # Start an instance of the file monitor, to keep track of log and results files
        with multiparser.FileMonitor(
            exception_callback=self.log_event,
            termination_trigger=self._trigger,
            flatten_data=True,
        ) as self.file_monitor:
            self._during_simulation()
            self.file_monitor.run()

        self._post_simulation()
