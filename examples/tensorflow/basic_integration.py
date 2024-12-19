"""
TensorFlow Connector Example
===============================
This is a basic example of the TensorVue Connector class.

This example trains a CNN which is trained on a 'mnist' dataset to recognise images of items of clothing

To run this example:
    - Move into TensorFlow examples directory: cd integrations/examples/tensorflow
    - Create a simvue.toml file, copying in your information from the Simvue server: vi simvue.toml
    - Install Poetry: pip install poetry
    - Install required modules: poetry install -E tensorflow
    - Run the example script: poetry run python basic_integration.py
    
For a more in depth example, see: https://docs.simvue.io/examples/tensorflow/
"""
import tensorflow as tf
from tensorflow import keras
import numpy
import matplotlib.pyplot as plt

# Firstly we import our Tensorflow integration:
import simvue_integrations.plugins.tensorflow as sv_tf

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

# At the most basic level, all we need to do is initialize our callback, providing a run name
tensorvue = sv_tf.TensorVue("recognising_clothes_basic")

# Train the model.
model.fit(
    img_train,
    label_train,
    epochs=5,
    validation_split=0.2,
    # Add the tensorvue class as a callback
    callbacks=[tensorvue,]
)

# That's it! Check your Simvue dashboard and you should see:
#    - A 'simulation' run, which summarises the overall training performance
#    - A number of 'epoch' runs, which show the training performed in each epoch

# You can also use the TensorVue callback to record results from model.evaluate
# Above we do it all in one step during the fitting, but you can also do it afterwards:
results = model.evaluate(
    img_test,
    label_test,
    # Add the tensorvue class as a callback
    callbacks=[tensorvue,]
)
# You should now also see an evaluation run, which records accuracy and loss from the test set separately

# Save the entire model as a `.keras` zip archive.
model.save('my_model.keras')