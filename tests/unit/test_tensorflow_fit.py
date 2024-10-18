import tensorflow as tf
from tensorflow import keras
import uuid
import simvue
import simvue_integrations.connectors.tensorflow as sv_tf
import tempfile
import pathlib
def test_fit_simulation_run(folder_setup, tensorflow_example_data):
    
    run_name = 'test_tensorflow_fit_no_epoch_run-%s' % str(uuid.uuid4())

    tensorvue = sv_tf.TensorVue(
        run_name=run_name,
        run_folder=folder_setup,
        create_epoch_runs=False
    )

    # Fit and evaluate the model, including the tensorvue callback:
    tensorflow_example_data.model.fit(
        tensorflow_example_data.img_train[:1000],
        tensorflow_example_data.label_train[:1000],
        epochs=3,
        validation_split=0.2,
        callbacks=[tensorvue,]
    )
    
    client = simvue.Client()
        
    # Check that one Simulation run and NO Epoch runs have been created
    runs = client.get_runs(filters=[f'name contains {run_name}'], metrics=True, metadata=True)
    assert len(runs) == 1
    
    # Check simulation run contains metadata for epoch, steps
    simulation_run = runs[0]
    assert simulation_run["metadata"].get("epochs")
    assert simulation_run["metadata"].get("steps")
    
    # Check accuracy, loss, val_accruracy, val_loss exist, have 3 steps (1 per epoch)
    for metric_name in ('accuracy','loss','val_accuracy','val_loss'):
        assert simulation_run["metrics"][metric_name]["count"] == 3
        
    # Check final model saved as output
    temp_dir = tempfile.TemporaryDirectory(prefix="tensorflow_test")
    client.get_artifacts_as_files(simulation_run["id"], "output", temp_dir.name)
    assert pathlib.Path(temp_dir.name).joinpath("final_model.keras").exists()    
    
        
        
def test_fit_epoch_run(folder_setup, tensorflow_example_data):
    
    run_name = 'test_tensorflow_fit_with_epoch_run-%s' % str(uuid.uuid4())

    tensorvue = sv_tf.TensorVue(
        run_name=run_name,
        run_folder=folder_setup,
    )

    # Fit and evaluate the model, including the tensorvue callback:
    tensorflow_example_data.model.fit(
        tensorflow_example_data.img_train[:1000],
        tensorflow_example_data.label_train[:1000],
        epochs=3,
        validation_split=0.2,
        callbacks=[tensorvue,]
    )
    
    client = simvue.Client()

    # Check that one Simulation run and NO Epoch runs have been created
    simulation_run = client.get_runs(filters=[f'name contains {run_name}_simulation'], metrics=True, metadata=True)
    epoch_runs = client.get_runs(filters=[f'name contains {run_name}_epoch'], metrics=True, metadata=True)
    assert len(simulation_run) == 1
    assert len(epoch_runs) == 3
    
    for epoch_run in epoch_runs:
        for metric_name in ('accuracy','loss','val_accuracy','val_loss'):
            # Check accuracy, loss, val_accruracy, val_loss metrics exist
            assert epoch_run["metrics"].get(metric_name)
            
            # Check metadata updated with final values of each
            assert epoch_run['metadata'].get(f"final_{metric_name}")
        
        # Check training progress events are logged
        events = [event['message'] for event in client.get_events(epoch_run['id'])]
        assert f"Training is 90% complete." in events
        assert "Accuracy and Loss values after epoch training:" in events
        
        
        
def test_fit_earlystopping(folder_setup, tensorflow_example_data):
    run_name = 'test_tensorflow_fit_earlystopping-%s' % str(uuid.uuid4())

    tensorvue = sv_tf.TensorVue(
        run_name=run_name,
        run_folder=folder_setup,
        create_epoch_runs=False,
        evaluation_parameter="accuracy",
        evaluation_condition=">",
        evaluation_target=0.8
    )

    # Fit and evaluate the model, including the tensorvue callback:
    tensorflow_example_data.model.fit(
        tensorflow_example_data.img_train[:1000],
        tensorflow_example_data.label_train[:1000],
        epochs=10,
        validation_split=0.2,
        callbacks=[tensorvue,]
    )
    client = simvue.Client()
    # Retrieve accuracy metric from the simulation run
    run_id = client.get_run_id_from_name(f"{run_name}_simulation")
    accuracy_metric = client.get_metric_values(run_ids=[run_id], metric_names=["accuracy"], xaxis="step", output_format="dataframe")
    accuracy_vals = accuracy_metric['accuracy'].tolist()
    
    # Check training was stopped early (not all 10 epochs were trained)
    assert len(accuracy_vals) < 10
    
    # Check final value is over 0.8, and second to last value is not over 0.8
    assert accuracy_vals[-1] > 0.8
    assert accuracy_vals[-2] < 0.8
    
    
    
    
    