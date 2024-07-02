import os
from simvue_integrations.wrappers.moose import MooseRun

with MooseRun() as run:
    # Initialize your Simvue run as normal
    run.init(
        name="moose-mug",
    )

    # Can add anything to the Simvue run which you want before / after the MOOSE simulation
    run.update_metadata({"user_name": "Matt F"})
    run.create_alert(
        name='handle_too_hot',
        source='metrics',
        metric='handle_temp_avg',
        rule='is above',
        threshold=323.15,
        frequency=1,
        window=1,
        trigger_abort=True
        )
    run.log_event("MOOSE simulation - coffee cup, terminating if handle too hot.") 
    
    # Call this to begin your MOOSE simulation
    run.launch(
        moose_application_path='app/moose_tutorial-opt',
        moose_file_path=os.path.join(os.path.dirname(__file__), 'example', 'steel_mug.i'),
        output_dir_path=os.path.join(os.path.dirname(__file__), 'example', 'results', 'steel'),
        results_prefix="mug_thermal",
    )

    # Again can add any custom data to the Simvue run
    run.log_event("Simulation is finished!")
    run.update_tags(["finished"])