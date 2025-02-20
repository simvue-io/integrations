import simvue
from examples.tensorflow.detailed_integration import tensorflow_example
import tempfile
import pathlib
import pytest
from simvue.sender import sender

@pytest.mark.parametrize("offline", (True, False), ids=("offline", "online"))
def test_tensorflow_connector(folder_setup, offline):
    
    run_name = tensorflow_example(folder_setup)

    if offline:
        _id_mapping = sender()
        
    client = simvue.Client()
    simulation_run = next(client.get_runs([f"folder.path == {folder_setup}", f'name contains {run_name}_simulation'], metadata=True, metrics=True, alerts=True))[1]
    epoch_runs = list(client.get_runs([f"folder.path == {folder_setup}", f'name contains {run_name}_epoch'], metadata=True, metrics=True, alerts=True))
    evaluation_run = next(client.get_runs([f"folder.path == {folder_setup}", f'name contains {run_name}_evaluation'], metadata=True, metrics=True, alerts=True))[1]
    
    # Check run description and tags from init have been added
    assert simulation_run.description == "A run to keep track of the training and validation of a Tensorflow model for recognising pieces of clothing."
    assert simulation_run.tags == ["tensorflow", "mnist_fashion", "simulation", "training"]
    
    # Check metadata uploaded to simulation run
    assert simulation_run.metadata.get("epochs")
    assert simulation_run.metadata.get("steps")
    
    metrics = dict(simulation_run.metrics)
    # Check accuracy, loss, val_accuracy, val_loss exist
    for metric_name in ('accuracy','loss','val_accuracy','val_loss'):
        assert metrics[metric_name]["count"] > 0
        
    # Check alert has been added
    assert "accuracy_below_seventy_percent" in [alert["name"] for alert in simulation_run.get_alert_details()]
        
    # Check final model saved as output
    temp_dir = tempfile.TemporaryDirectory(prefix="tensorflow_test")
    client.get_artifacts_as_files(simulation_run.id, "output", temp_dir.name)
    assert pathlib.Path(temp_dir.name).joinpath("final_model.keras").exists()
    
    # Check 5 epoch runs exist
    assert len(epoch_runs) == 5
    
    epoch_run = epoch_runs[0][1]
    metrics = dict(epoch_run.metrics)
    
    # Check epoch run contains accuracy, loss, val_accuracy, val_loss
    for metric_name in ('accuracy','loss','val_accuracy','val_loss'):
        assert metrics[metric_name]["count"] > 0
        
    # Check alert has been added
    assert "accuracy_below_seventy_percent" in [alert["name"] for alert in epoch_run.get_alert_details()]
    
    # Check checkpoint model files uploaded as outputs to Epoch run
    client.get_artifacts_as_files(epoch_run.id, "output", temp_dir.name)
    assert pathlib.Path(temp_dir.name).joinpath("checkpoint.model.keras").exists()
    
    metrics = dict(evaluation_run.metrics)
    # Check accuracy, loss, exist in evaluation run
    for metric_name in ('accuracy','loss'):
        assert metrics[metric_name]["count"] > 0
        
    # Check val_accuracy and val_loss dont exist
    for metric_name in ('val_accuracy','val_loss'):
        assert not metrics.get(metric_name, None)
        
    # Check alert has not been added
    assert "accuracy_below_seventy_percent" not in [alert["name"] for alert in evaluation_run.get_alert_details()]
    