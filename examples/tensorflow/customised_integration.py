# example of integrating Simvue into a Tensorflow Keras CNN with customised options

import tensorflow as tf
from tensorflow import keras
import numpy
import matplotlib.pyplot as plt

# Firstly we import our Tensorflow integration:
import simvue_integrations.tensorflow.tensorvue as sv_tf

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

# Say we want to upload an image of our results to the Simvue server once the training is complete
# To do this we create a custom TensorVue class, inheriting from TensorVue:
class MyTensorVue(sv_tf.TensorVue):

    # We will add the following attributes after initializing the class:
    # self.img_predict
    # self.label_predict
    # self.class_names

    # This method will be called whenever a training session ends
    def on_train_end(self, logs):
        predictions = model.predict(self.img_predict)
        overall_guess = numpy.argmax(predictions, axis=1)

        # Change colours of labels based on whether prediction is correct / incorrect
        correct_colour = ["green" if guess == self.label_predict[i] else "red" for i, guess in enumerate(overall_guess)]

        # Plot images, with the results from the neural network for each
        plt.figure(figsize=(10,10))
        for i in range(25):
            plt.subplot(5,5,i+1)
            plt.xticks([])
            plt.yticks([])
            plt.grid(False)
            plt.imshow(img_test[i], cmap=plt.cm.binary)
            plt.xlabel(self.class_names[overall_guess[i]], color=correct_colour[i])
        plt.savefig("predictions.png")

        # Upload as artifact to simulation run
        self.simulation_run.save("predictions.png", "output")

        # Don't forget to then call the base TensorVue method!
        super().on_train_end(logs)

# Then initialize this class:
tensorvue = MyTensorVue(
    "recognising_clothes_custom",
    # And any other details you want to provide...
)
# And initialize those attributes
tensorvue.img_predict = img_test[:25]
tensorvue.label_predict = label_test[:25]
tensorvue.class_names = ['T-shirt/top', 'Trouser', 'Pullover', 'Dress', 'Coat', 'Sandal', 'Shirt', 'Sneaker', 'Bag', 'Ankle boot']

# Train the model.
model.fit(
    img_train,
    label_train,
    epochs=10,
    validation_split=0.2,
    # Add the tensorvue class as a callback
    callbacks=[tensorvue,]
)

# Once training is complete, you should see that the results image has been uploaded as an Output artifact to the run!