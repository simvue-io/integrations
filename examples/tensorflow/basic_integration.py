# Basic example of integrating Simvue into a Tensorflow Keras CNN
# At the most basic level, it only takes the addition of three lines to your model code!
# As an example, we will look at a CNN which is trained on the 'mnist' dataset to recognise images of hand drawn numbers
# Thanks to https://victorzhou.com/blog/keras-cnn-tutorial/ for the CNN model

import mnist
import numpy as np
from tensorflow.keras.callbacks import ModelCheckpoint
from tensorflow.keras.layers import Conv2D, Dense, Flatten, MaxPooling2D
from tensorflow.keras.models import Sequential
from tensorflow.keras.utils import to_categorical

# Firstly we import our Tensorflow integration:
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

# At the most basic level, all we need to do is initialize our callback, providing a run name
tensorvue = sv_tf.TensorVue("tf_demo")

# Train the model.
model.fit(
    train_images,
    to_categorical(train_labels),
    epochs=4,
    validation_data=(test_images, to_categorical(test_labels)),
    # We then include the initialized Callback in our list of callbacks when fitting our model
    callbacks=[
        tensorvue,
    ],
)

# That's it! Check your Simvue dashboard and you should see:
#    - A 'simulation' run, which summarises the overall training performance
#    - A number of 'epoch' runs, which show the training performed in each epoch

# You can also use the TensorVue callback to record results from model.evaluate
# Above we do it all in one step during the fitting, but you can also do it afterwards:
model.evaluate(
    test_images,
    to_categorical(test_labels),
    callbacks=[
        tensorvue,
    ],
)
# You should now also see an evaluation run, which records accuracy and loss from the test set separately
