import simvue
import multiparser
import multiprocessing


class WrappedRun(simvue.Run):
    """Generic wrapper to the Run class which can be used to build Connectors to non-python applications.

    New Connectors should inherit from this class, and override the specific methods below to add functionality
    for their given application. Make sure to call the base method as well.
    """

    def pre_simulation(self):
        """Method which runs after launch() is called, but before a simulation begins.

        By default, creates a termination trigger for the FileMonitor to use, and checks that a Simvue run has
        been initialised. This method should be called BEFORE the rest of your functions in the overriden method.
        """
        self._trigger = multiprocessing.Event()

        if not self._simvue:
            self._error("Run must be initialized before launching the simulation.")
            return False

    def during_simulation(self):
        """Method which runs after launch() is called and after the simulation begins, within the FileMonitor."""
        pass

    def post_simulation(self):
        """Method which runs after launch() is called and after the simulation finishes."""
        pass

    def launch(self):
        """Method which launches the simulation and the monitoring.

        By default calls the three methods above, and sets up a FileMonitor for tracking files.
        """
        self.pre_simulation()

        # Start an instance of the file monitor, to keep track of log and results files
        with multiparser.FileMonitor(
            exception_callback=self.log_event,
            termination_trigger=self._trigger,
            flatten_data=True,
        ) as self.file_monitor:
            self.during_simulation()
            self.file_monitor.run()

        self.post_simulation()
