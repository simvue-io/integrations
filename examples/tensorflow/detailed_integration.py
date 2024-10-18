# More detailed example of integrating Simvue into a Tensorflow Keras CNN
# Uses a number of different options and callbacks to get more out of your Simvue integration

import tensorflow as tf
from tensorflow import keras
import numpy
import matplotlib.pyplot as plt
from tensorflow.keras.callbacks import ModelCheckpoint

# Firstly we import our Tensorflow integration:
import simvue_integrations.connectors.tensorflow as sv_tf

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
checkpoint_filepath = "/tmp/ckpt/checkpoint.model.keras"
model_checkpoint_callback = ModelCheckpoint(
    filepath=checkpoint_filepath, save_best_only=False, verbose=1
)


# We then instantiate our TensorVue class, but include a number of additional options
tensorvue = sv_tf.TensorVue(
    # Can define additional info, like the folder, description, and tags for the runs
    run_name="recognising_clothes_detailed",
    run_folder="/recognising_clothes_v2",
    run_description="A run to keep track of the training and validation of a Tensorflow model for recognising pieces of clothing.",
    run_tags=["tensorflow", "mnist_fashion"],

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

    # Will stop training early if the accuracy of the model exceeds 95%
    evaluation_condition=">",
    evaluation_parameter="accuracy",
    evaluation_target=0.95,

    # Choose where the final model is saved
    model_final_filepath="tf_fashion_model.keras"
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

# Save the entire model as a `.keras` zip archive.
model.save('my_model.keras')

# You can see a visual representation of the accuracy by doing the following:

# Map the label numbers to their corresponding human readable strings:
class_names = ['T-shirt/top', 'Trouser', 'Pullover', 'Dress', 'Coat', 'Sandal', 'Shirt', 'Sneaker', 'Bag', 'Ankle boot']

predictions = model.predict(img_test[:25])
overall_guess = numpy.argmax(predictions, axis=1)

# Change colours of labels based on whether prediction is correct / incorrect
correct_colour = ["green" if guess == label_test[i] else "red" for i, guess in enumerate(overall_guess)]

# Plot images, with the results from the neural network for each
plt.figure(figsize=(10,10))
for i in range(25):
    plt.subplot(5,5,i+1)
    plt.xticks([])
    plt.yticks([])
    plt.grid(False)
    plt.imshow(img_test[i], cmap=plt.cm.binary)
    plt.xlabel(class_names[overall_guess[i]], color=correct_colour[i])
plt.show()