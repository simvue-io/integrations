import pytest
import simvue
import uuid
import subprocess
from tensorflow import keras

@pytest.fixture(scope='session', autouse=True)
def folder_setup():
    # Will be executed before the first test
    folder  = '/tests-connectors-%s' % str(uuid.uuid4())
    yield folder
    # Will be executed after the last test
    client = simvue.Client()
    client.delete_folder(folder, remove_runs=True)
    
    
@pytest.fixture()
def tensorflow_example_data():
    class TensorflowExample():
        def __init__(self):
            # Load the training and test data
            (img_train, self.label_train), (img_test, self.label_test) = keras.datasets.fashion_mnist.load_data()

            # Normalize pixel values between 0 and 1
            self.img_train = img_train.astype('float32') / 255.0
            self.img_test = img_test.astype('float32') / 255.0

            # Create a basic model
            model = keras.Sequential()

            model.add(keras.layers.Flatten(input_shape=(28, 28)))
            model.add(keras.layers.Dense(32, activation='relu'))
            model.add(keras.layers.Dense(10))

            model.compile(optimizer=keras.optimizers.Adam(learning_rate=0.01),
                        loss=keras.losses.SparseCategoricalCrossentropy(from_logits=True),
                        metrics=['accuracy'])
            
            self.model = model
            
    return TensorflowExample()
        
