# More detailed example of integrating Simvue into a Tensorflow Keras CNN
# Uses a number of different options and callbacks to get more out of your Simvue integration

import mnist
import numpy as np
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
from tensorflow.keras.layers import Conv2D, Dense, Flatten, MaxPooling2D
from tensorflow.keras.models import Sequential
from tensorflow.keras.utils import to_categorical

# As before, import the integration
import simvue_integrations.tensorflow.tensorvue as sv_tf

# Get images from mnist
train_images = mnist.train_images()
train_labels = mnist.train_labels()
test_images = mnist.test_images()
test_labels = mnist.test_labels()

# Normalize the images.
train_images = (train_images / 255) - 0.5
test_images = (test_images / 255) - 0.5

# Reshape the images.
train_images = np.expand_dims(train_images, axis=3)
test_images = np.expand_dims(test_images, axis=3)

# Define some constants
num_filters = 8
filter_size = 3
pool_size = 2

# Build the model.
model = Sequential(
    [
        Conv2D(num_filters, filter_size, input_shape=(28, 28, 1)),
        MaxPooling2D(pool_size=pool_size),
        Flatten(),
        Dense(10, activation="softmax"),
    ]
)

# Compile the model.
model.compile(
    "adam",
    loss="categorical_crossentropy",
    metrics=["accuracy"],
)

# Can use the ModelCheckpoint callback, which is built into Tensorflow, to save a model after each Epoch
# Provinding the model_checkpoint_filepath in the TensorVue callback means it will automatically upload checkpoints to the Epoch runs
checkpoint_filepath = "/tmp/ckpt/checkpoint.model.keras"
model_checkpoint_callback = ModelCheckpoint(
    filepath=checkpoint_filepath, save_best_only=False, verbose=1
)

# Can use the EarlyStopping callback, built into Tensorflow, to prevent overtraining by stopping execution if one of the metrics stops improving
# This will restore the model to the best epoch found, which Simvue will then save to the Simulation run
early_stopping = EarlyStopping(restore_best_weights=True, patience=2, verbose=1)

tensorflow = sv_tf.TensorVue(
    # Can define additional info, like the folder, description, and tags for the runs
    "tf_demo",
    "/tf_testing",
    "A run to check how tensorflow callbacks work.",
    ["tensorflow", "testing"],
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
    start_alerts_from_epoch=2,
    # Saves the checkpoint model after each epoch
    model_checkpoint_filepath=checkpoint_filepath,
)

# Train the model.
model.fit(
    train_images,
    to_categorical(train_labels),
    epochs=20,
    validation_data=(test_images, to_categorical(test_labels)),
    callbacks=[early_stopping, model_checkpoint_callback, tensorflow],
)
