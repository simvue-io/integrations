"""
TensorFlow Connector Example
===============================
This is a more detailed example of the TensorVue Connector class, showing more functionality.

This example trains a CNN which is trained on a 'mnist' dataset to recognise images of items of clothing

To run this example:
    - Move into TensorFlow examples directory: cd integrations/examples/tensorflow
    - Create a simvue.toml file, copying in your information from the Simvue server: vi simvue.toml
    - Install Poetry: pip install poetry
    - Install required modules: poetry install -E tensorflow
    - Run the example script: poetry run python detailed_integration.py
"""
import tensorflow as tf
from tensorflow import keras
import uuid
import tempfile
import pathlib
from tensorflow.keras.callbacks import ModelCheckpoint

# Firstly we import our Tensorflow integration:
import simvue_integrations.plugins.tensorflow as sv_tf

def tensorflow_example(run_folder, offline=False):
    # Load the training and test data
    (img_train, label_train), (img_test, label_test) = keras.datasets.fashion_mnist.load_data()

    # Normalize pixel values between 0 and 1
    img_train = img_train.astype('float32') / 255.0
    img_test = img_test.astype('float32') / 255.0

    # Create a basic model
    model = keras.Sequential()

    model.add(keras.layers.Flatten(input_shape=(28, 28)))
    model.add(keras.layers.Dense(32, activation='relu'))
    model.add(keras.layers.Dense(10))

    model.compile(optimizer=keras.optimizers.Adam(learning_rate=0.01),
                loss=keras.losses.SparseCategoricalCrossentropy(from_logits=True),
                metrics=['accuracy'])

    # Can use the ModelCheckpoint callback, which is built into Tensorflow, to save a model after each Epoch
    # Providing the model_checkpoint_filepath in the TensorVue callback means it will automatically upload checkpoints to the Epoch runs
    temp_dir = tempfile.TemporaryDirectory()
    checkpoint_filepath = str(pathlib.Path(temp_dir.name).joinpath("checkpoint.model.keras"))
    model_checkpoint_callback = ModelCheckpoint(
        filepath=checkpoint_filepath, save_best_only=False, verbose=1
    )

    run_name = "recognising_clothes_detailed-%s" % str(uuid.uuid4())
    # We then instantiate our TensorVue class, but include a number of additional options
    tensorvue = sv_tf.TensorVue(
        # Can define additional info, like the folder, description, and tags for the runs
        run_name=run_name,
        run_folder=run_folder,
        run_description="A run to keep track of the training and validation of a Tensorflow model for recognising pieces of clothing.",
        run_tags=["tensorflow", "mnist_fashion"],
        run_mode="offline" if offline else "online",

        # Can define alerts:
        alert_definitions={
            "accuracy_below_seventy_percent": {
                "source": "metrics",
                "rule": "is below",
                "metric": "accuracy",
                "frequency": 1,
                "window": 1,
                "threshold": 0.7,
            }
        },

        # And different alerts can be applied to the Simulation, Epoch or Validation runs
        simulation_alerts=["accuracy_below_seventy_percent"],
        epoch_alerts=["accuracy_below_seventy_percent"],
        start_alerts_from_epoch=3,

        # Saves the checkpoint model after each epoch
        model_checkpoint_filepath=checkpoint_filepath,

        # Will stop training early if the accuracy of the model exceeds 99%
        evaluation_condition=">",
        evaluation_parameter="accuracy",
        evaluation_target=0.99,

        # Choose where the final model is saved
        model_final_filepath=str(pathlib.Path(temp_dir.name).joinpath("tf_fashion_model.keras"))
    )

    # Fit and evaluate the model, including the tensorvue callback:
    model.fit(
        img_train,
        label_train,
        epochs=5,
        validation_split=0.2,
        # Specify the model callback, BEFORE the tensorvue callback in the list:
        callbacks=[model_checkpoint_callback, tensorvue,]
    )
    results = model.evaluate(
        img_test,
        label_test,
        # Add the tensorvue class as a callback
        callbacks=[tensorvue,]
    )
    return run_name
    
if __name__ == "__main__":
    tensorflow_example("/recognising_clothes_v2")