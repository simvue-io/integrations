import tensorflow as tf
from tensorflow import keras
import uuid
import simvue
import simvue_integrations.plugins.tensorflow as sv_tf

def test_fit_evaluation_run(folder_setup, tensorflow_example_data):
    
    run_name = 'test_tensorflow_eval-%s' % str(uuid.uuid4())

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
    )
    
    results = tensorflow_example_data.model.evaluate(
        tensorflow_example_data.img_test,
        tensorflow_example_data.label_test,
        callbacks=[tensorvue]
    )    
    
    client = simvue.Client()
        
    # Check that one Evaluation run
    runs = list(client.get_runs(filters=[f'name contains {run_name}'], metrics=True, metadata=True))
    
    assert len(runs) == 1
    
    # Since this returns a tuple of ID and Run for each instance, but we just want the Run object, use [1]
    eval_run = runs[0][1]
    
    metrics = dict(eval_run.metrics)
    
    # Check accuracy and loss metrics exist
    for metric_name in ('accuracy','loss'):
        assert metrics.get(metric_name)
    
    assert [metrics["loss"]["last"], metrics["accuracy"]["last"]] == results        
    