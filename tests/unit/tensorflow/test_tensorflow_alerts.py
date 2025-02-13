import tensorflow as tf
from tensorflow import keras
import uuid
import simvue
import simvue_integrations.plugins.tensorflow as sv_tf
from simvue_integrations.extras.validators import AlertValidator
import pytest
import pydantic

def test_adding_alerts(folder_setup, tensorflow_example_data):
    
    run_name = 'test_tensorflow_eval-%s' % str(uuid.uuid4())

    tensorvue = sv_tf.TensorVue(
        run_name=run_name,
        run_folder=folder_setup,
        alert_definitions={
            "accuracy_below_80_percent": {
                "source": "metrics",
                "rule": "is below",
                "metric": "accuracy",
                "frequency": 1,
                "window": 1,
                "threshold": 0.8,
                "trigger_abort": False,
                "notification": "email",
            },
            "loss_above_half": {
                "source": "metrics",
                "rule": "is above",
                "metric": "loss",
                "frequency": 1,
                "window": 1,
                "threshold": 0.5,
                "trigger_abort": False,
                "notification": "email",
            },
            "model_diverged": {
                "source": "events",
                "frequency": 1,
                "pattern": "Model diverged with loss = NaN",
            },
        },
        simulation_alerts=["loss_above_half", "model_diverged"],
        evaluation_alerts=["loss_above_half","accuracy_below_80_percent"],
        epoch_alerts=["accuracy_below_80_percent"],
        start_alerts_from_epoch=2
        
        
    )

    # Fit and evaluate the model, including the tensorvue callback:
    tensorflow_example_data.model.fit(
        tensorflow_example_data.img_train[:1000],
        tensorflow_example_data.label_train[:1000],
        epochs=3,
        validation_split=0.2,
        callbacks=[tensorvue]
    )
    
    results = tensorflow_example_data.model.evaluate(
        tensorflow_example_data.img_test,
        tensorflow_example_data.label_test,
        callbacks=[tensorvue]
    )    

    client = simvue.Client()
    
    # Retrieve each type of alert from server
    simulation_run = next(client.get_runs(filters=[f'name contains {run_name}_simulation'], alerts=True))[1]
    evaluation_run = next(client.get_runs(filters=[f'name contains {run_name}_evaluation'], alerts=True))[1]
    epoch_run_1 = next(client.get_runs(filters=[f'name contains {run_name}_epoch_1'], alerts=True))[1]
    epoch_run_2 = next(client.get_runs(filters=[f'name contains {run_name}_epoch_2'], alerts=True))[1]
    epoch_run_3 = next(client.get_runs(filters=[f'name contains {run_name}_epoch_3'], alerts=True))[1]
        
    # Check simulaiton run has one alert added, and that is 'loss_above_half'
    assert len(simulation_run.alerts) == 2
    assert sorted([alert["name"] for alert in simulation_run.get_alert_details()]) == sorted(["loss_above_half", "model_diverged"])
    
    # Check evaluation run has both alerts added
    assert len(evaluation_run.alerts) == 2
    assert sorted([alert["name"] for alert in evaluation_run.get_alert_details()]) == sorted(["accuracy_below_80_percent", "loss_above_half"])
    
    # Check first epoch run has no alerts defined, since alerts should start from epoch 2
    assert len(epoch_run_1.alerts) == 0
    
    # Check epoch runs 2 and 3 each have one alert defined, and that is 'accuracy_below_80_percent'
    assert len(epoch_run_2.alerts) == 1
    assert next(epoch_run_2.get_alert_details())["name"] == "accuracy_below_80_percent"
    assert len(epoch_run_3.alerts) == 1
    assert next(epoch_run_3.get_alert_details())["name"] == "accuracy_below_80_percent"
            
    
    
invalid_alerts = [
    # Missing required 'metric' kwarg
    {
        "source": "metrics",
        "rule": "is below",
        "frequency": 1,
        "window": 1,
        "threshold": 0.8,
    },
    # Cannot have 'pattern' kwarg when source is metrics
    {
        "source": "metrics",
        "pattern": "wrong",
        "rule": "is below",
        "metric": "accuracy",
        "frequency": 1,
        "window": 1,
        "threshold": 0.8,
    },
    # Invalid 'source' input
    {
        "source": "alerts",
        "rule": "is below",
        "metric": "accuracy",
        "frequency": 1,
        "window": 1,
        "threshold": 0.8,
    },
    # Invalid type for 'frequency'
    {
        "source": "metrics",
        "rule": "is below",
        "metric": "accuracy",
        "frequency": "one",
        "window": 1,
        "threshold": 0.8,
    },
    # Unexpected kwarg 'new'
    {
            "source": "metrics",
            "rule": "is below",
            "metric": "accuracy",
            "frequency": "one",
            "window": 1,
            "threshold": 0.8,
            "new": "hi"
        },
    # Shouldn't specify aggregation when source is events
    {
            "source": "events",
            "frequency": 1,
            "pattern": "test pattern",
            "aggregation": "sum",
        },
]

@pytest.mark.parametrize("alert_definitions", invalid_alerts)
def test_invalid_alert_configs(alert_definitions):
    with pytest.raises(pydantic.ValidationError):
        AlertValidator(**alert_definitions)