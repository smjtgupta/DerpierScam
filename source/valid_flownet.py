from __future__ import absolute_import
import cv2
import os
import h5py
import numpy as np
import numpy.matlib as matlib
import scipy.io as sio
#from ImageDataGenerator import ImageDataGenerator
#from keras.preprocessing.image import ImageDataGenerator
from keras import optimizers
from keras.models import Sequential
from keras.layers import Convolution2D, MaxPooling2D, ZeroPadding2D, AtrousConvolution2D, UpSampling2D, Deconvolution2D
from keras.layers import Convolution1D, ZeroPadding1D
from keras.layers import Activation, Dropout, Flatten, Dense, Lambda, Reshape, Permute, Cropping2D, merge, Embedding
from keras import backend as K
from keras.callbacks import ModelCheckpoint, LearningRateScheduler, TensorBoard
from keras.objectives import categorical_crossentropy
from keras.engine.training import weighted_objective
import tensorflow as tf
from functools import partial
from itertools import product
from keras.utils.np_utils import convert_kernel
import code

# for vgg
import warnings

from keras.models import Model
from keras.layers import Flatten, Dense, Input
from keras.layers import Convolution2D, MaxPooling2D
from keras.utils.layer_utils import convert_all_kernels_in_model
from keras.utils.data_utils import get_file
from keras import backend as K
from keras.applications.imagenet_utils import decode_predictions, preprocess_input

# for custom scaling
from keras import backend as K
from keras.engine.topology import Layer

import numpy as np
import warnings

from keras.layers import merge, Input
from keras.layers import AveragePooling2D
from keras.layers import BatchNormalization
from keras.models import Model
from keras.utils.layer_utils import convert_all_kernels_in_model
from keras.utils.data_utils import get_file
#from keras.magenet_utils import decode_predictions, preprocess_input

K.set_image_dim_ordering('tf')  # Tensorflow ordering from now on
num_channels = 1

matfiles = ['../maps/corrected_rib.mat', '../maps/corrected_groel.mat']
weights_path = '../models/vgg16_tf.h5'
train_raw_npy = '../data/train/train_im.npy'
train_label_npy = '../data/train_cam_gt.npy'
checkpoint_file = 'mynet.hdf5'

input_size = 256 
batch_size = 32
num_pairs = 10000  # pairs generated each epoch
num_outputs = 4

subtract_mean = 0
nb_epoch = 1  # we have to generate new data each epoch
#num_outputs = 2
 

def expand_dims(layers):
    return K.expand_dims(layers)


# create data given directory containing all images and list
def create_data(data_path, list_file, npy_file, zoom=8,is_label=False):
    pass   

def load_data(matfiles):
# loads data into arrays
# assume matfiles of 2048 images
    img_size = 256
    imgs = np.zeros((img_size,img_size,0))
    quats = np.zeros((4,0))

    for i in range(len(matfiles)):
        temp = sio.loadmat(matfiles[i])
        imgs = np.concatenate((imgs,temp['clean_projections']),axis=2)
        quats = np.concatenate((quats,temp['q']),axis = 1)
  
    imgs = np.expand_dims(imgs,axis = 3) 

    return imgs, quats

def gen_data(imgs,quats,num_pairs=2048):
# creates pairwise image stacks
    imgs_per_mat = 2048
    img_size = 256
    num_imgs = imgs.shape[2]
    pairs = np.random.randint(num_imgs,size=(num_pairs,2))
    img_pairs = np.zeros((num_pairs,img_size,img_size,2))
    img_rot = np.zeros((num_pairs,4))
    img_label = np.zeros((num_pairs,1))

    for i in range(num_pairs):
        a = pairs[i,0]
        b = pairs[i,1]
        img_pairs[i] = np.concatenate((imgs[:,:,a],imgs[:,:,b]),axis=2)
        img_label[i] = 1 * ( (a/imgs_per_mat) == (b/imgs_per_mat) )
        img_rot[i] = img_label[i] * quatmultiply(quats[:,b], quatinv(quats[:,a]))

    return img_pairs, img_rot, img_label


def quatinv(q):
    return np.array([q[0],-q[1],-q[2],-q[3] ] )

def quatmultiply(q,r):
    q0 = q[0]; q1 = q[1]; q2 = q[2]; q3 = q[3];
    r0 = r[0]; r1 = r[1]; r2 = r[2]; r3 = r[3];
    t0=(r0*q0-r1*q1-r2*q2-r3*q3)
    t1=(r0*q1+r1*q0-r2*q3+r3*q2)
    t2=(r0*q2+r1*q3+r2*q0-r3*q1)
    t3=(r0*q3-r1*q2+r2*q1+r3*q0)
    return np.array([t0, t1, t2, t3])

def euclidean_distance(vects):
    x, y = vects
    return K.sqrt(K.sum(K.square(x - y), axis=1, keepdims=True))


def eucl_dist_output_shape(shapes):
    shape1, shape2 = shapes
    return (shape1[0], 1)


def contrastive_loss(y_true, y_pred):
    '''Contrastive loss from Hadsell-et-al.'06
    http://yann.lecun.com/exdb/publis/pdf/hadsell-chopra-lecun-06.pdf
    '''
    margin = 1
    return K.mean(y_true * K.square(y_pred) + (1 - y_true) * K.square(K.maximum(margin - y_pred, 0)))



def load_net(weights_path,num_outputs=num_outputs,input_size=input_size):
    return vgg_siam_like(weights_path,num_outputs=num_outputs,input_size=input_size)

def create_feature_extraction_network(input_shape):
    inputs = Input(shape = input_shape) 
    # layer 1 (size = 256x256)
    conv1 = Convolution2D(64, 3, 3, border_mode = 'same', activation='relu',name='conv1_1')(inputs)
    conv1 = Convolution2D(64, 3, 3, border_mode = 'same', activation='relu',name='conv1_2')(conv1)
    pool1 = MaxPooling2D(pool_size=(2, 2))(conv1)
    # layer 2 (size = 128x128)
    conv2 = Convolution2D(128, 3, 3, border_mode = 'same', activation='relu',name='conv2_1')(pool1)
    conv2 = Convolution2D(128, 3, 3, border_mode = 'same', activation='relu',name='conv2_2')(conv2)
    pool2 = MaxPooling2D(pool_size=(2, 2))(conv2)
    # layer 3 (size = 64*64)
    conv3 = Convolution2D(256, 3, 3, border_mode = 'same', activation='relu',name='conv3_1')(pool2)
    conv3 = Convolution2D(256, 3, 3, border_mode = 'same', activation='relu',name='conv3_2')(conv3)
    conv3 = Convolution2D(256, 3, 3, border_mode = 'same', activation='relu',name='conv3_3')(conv3)
    pool3 = MaxPooling2D(pool_size=(2, 2))(conv3)
    # layer 4 (size = 32*32)
    conv4 = Convolution2D(512, 3, 3, border_mode = 'same', activation='relu',name='conv4_1')(pool3)
    conv4 = Convolution2D(512, 3, 3, border_mode = 'same', activation='relu',name='conv4_2')(conv4)
    conv4 = Convolution2D(512, 3, 3, border_mode = 'same', activation='relu',name='conv4_3')(conv4)
    pool4 = MaxPooling2D(pool_size=(2, 2))(conv4)
    # layer 5 (size = 16*16)
    conv5 = Convolution2D(512, 3, 3, border_mode = 'same', activation='relu',name='conv5_1')(pool4)
    conv5 = Convolution2D(512, 3, 3, border_mode = 'same', activation='relu',name='conv5_2')(conv5)
    conv5 = Convolution2D(512, 3, 3, border_mode = 'same', activation='relu',name='conv5_3')(conv5)
    pool5 = MaxPooling2D(pool_size=(2, 2))(conv5)
    # result (size = 8x8)
    pool5 = Flatten(name='flatten')(pool5)
    # result (size = 64)
    return Model(inputs,pool5)

def vgg_siam_like(weights_path=None, num_outputs=num_outputs,input_size=None): 
    #num_channels = num_channels
    if K.image_dim_ordering() == 'th':
        concat_axis = 1
        input_shape = (num_channels,input_size,input_size)
    else:
        concat_axis = 3
        input_shape = (input_size,input_size,num_channels)

    # feature extraction
    feature_network = create_feature_extraction_network(input_shape)

    # top feature extraction tower
    inputTop = Input(shape=input_shape, name = 'input_top')
    featureTop = feature_network(inputTop)
    
    # bottom feature extraction tower
    inputBot = Input(shape=input_shape, name = 'input_bot')
    featureBot = feature_network(inputBot)
    


    # correlate two features using a custom filter (custom_corr)
    # don't have this yet, will use concat for now
    featureTopExpand = Lambda(expand_dims,name='expand_top')(featureTop)
    featureBotExpand = Lambda(expand_dims,name='expand_bot')(featureBot)

    custom_corr = merge([featureTopExpand, featureTopExpand], mode='concat', concat_axis=2)
    #print(custom_corr.shape)
    # crm layers
    #
    conv6 = Convolution1D(16, 3, border_mode = 'same', activation='relu',name='conv6_1')(custom_corr)
    conv6 = Convolution1D(16, 3, border_mode = 'same', activation='relu',name='conv6_2')(conv6)
    #pool6 = MaxPooling2D(pool_size=(2, 2))(conv4)
    #
    conv7 = Convolution1D(32, 3, border_mode = 'same', activation='relu',name='conv7_1')(conv6)
    conv7 = Convolution1D(32, 3, border_mode = 'same', activation='relu',name='conv7_2')(conv7)
    pool7 = Flatten(name='flatten')(conv7)

    # keeping fc small for now to keep num parameters small
    # camera pose estimation layer
    fc3 = Dense(128, activation='relu', name='fc1')(pool7)
    fc4 = Dense(128, activation='relu', name='fc2')(fc3)
    rotation_output = Dense(num_outputs, name='rotation')(fc4) #any activation needed here???????????


    # virus classification layer
    fc11 = Dense(128, activation='relu', name='fc1_1')(featureTop)
    fc12 = Dense(128, activation='relu', name='fc1_2')(fc11)
    fc21 = Dense(128, activation='relu', name='fc2_1')(featureBot)
    fc22 = Dense(128, activation='relu', name='fc2_2')(fc21)
    #classification_output = Dense(1, activation='sigmoid', name='classifier')(fc2)
    classification_output = Lambda(euclidean_distance, output_shape=eucl_dist_output_shape,name='classification')([fc12, fc22])


    model = Model(input = [inputTop, inputBot], output=[rotation_output, classification_output])

    #assert os.path.exists(weights_path), 'Model weights not found (see "weights_path" variable in script).'
    #model.load_weights(weights_path, by_name=True)
    model.summary()

    print('Model loaded.')

    return model

'''
def train(finetune=False,lr=1e-3):
    print('-'*30)
    print('Loading and preprocessing train data...')
    print('-'*30)
   

    imgs, quats = load_data(matfiles)

    print('-'*30)
    print('Creating and compiling model...')
    print('-'*30)

    model = load_net(weights_path,input_size=input_size)
    if finetune:
        print("Finetuning using", checkpoint_file)
        model.load_weights(checkpoint_file)

    model_checkpoint = ModelCheckpoint(checkpoint_file, monitor='loss' )

    print('-'*30)
    print('Fitting model...')
    print('-'*30)
    
    model.compile(loss=['mse',contrastive_loss], loss_weights=[5.0, 1.0],
                  optimizer=optimizers.Adam(lr=lr, beta_1=0.9, beta_2=0.999, epsilon=1e-08, decay=0.0),
                  metrics=['mse', 'accuracy'] )

    for i in range(5): # num times to drop learning rate
        print('Learning rate: {0}'.format(lr))
        K.set_value(model.optimizer.lr, lr)

        for j in range(100): # num times to generate data ~8M images
            print('(i,j)=({0},{1})'.format(i,j))
            img_pairs, rotations, labels = gen_data(imgs,quats,num_pairs=num_pairs)
            input_top = np.expand_dims(img_pairs[:,:,:,0], axis=3)
            input_bot = np.expand_dims(img_pairs[:,:,:,1], axis=3)
            model.fit([ input_top, input_bot ], 
                      [ rotations, labels ], batch_size=batch_size,
                      nb_epoch=nb_epoch, validation_split=.05, verbose=1, 
                      callbacks=[model_checkpoint])  #modify input and output here into 2 vectors

        lr = lr *.1
'''
def predict(image_file):
    #palette = np.array([[0,0,0],[0,255,0],[255,0,0],[0,0,255],[255,0,255]],dtype=np.uint8)
 
    #print ("Loading Image") 
    #img = cv2.imread(image_file)
    #transformed_img = img.astype(np.float32) - subtract_mean

    model = load_net(weights_path,num_outputs=num_outputs,input_size=img.shape)
    model.load_weights(checkpoint_file)

    if K.image_dim_ordering() == 'th':
        transformed_img = transformed_img.transpose(2,0,1)

    transformed_img = np.expand_dims(transformed_img,axis=0)

    if num_channels == 1:
        transformed_img = transformed_img[:,:,:,0]
        transformed_img = np.expand_dims(transformed_img,axis=3)
    
    image_size = img.shape
   
    print ("Predicting")
    prediction = model.predict(transformed_img, verbose=1)
    print prediction.shape
    prediction = prediction[0]
  

def validate():
    #K.learning_phase(0)
    #img_rib = (sio.loadmat(matfiles[0]))['clean_projections']
    #test_rib1 = img_rib[1]
    #test_rib2 = img_rib[2]
    #rot_rib = (sio.loadmat(matfiles[0]))['']	
    #test_rot1 = rot_rib[1]
    #test_rot2 = rot_rib[2]
    #ideal_rot = quatmultiply(test_rot2, quatinv(test_rot1))
    #imgs_mask_test = model.predict(imgs_test, verbose=1)
    imgs, quats = load_data(matfiles)
    img_pairs, rotations, labels = gen_data(imgs,quats,num_pairs=10)
    
    model = load_net(weights_path,num_outputs=num_outputs,input_size=input_size)
    model.load_weights(checkpoint_file)

    input_top = np.expand_dims(img_pairs[:,:,:,0], axis=3)
    input_bot = np.expand_dims(img_pairs[:,:,:,1], axis=3)

    rots, vclass = model.predict([input_top,input_bot])
    
    np.save('truerot.npy',rotations)
    np.save('predrot.npy',rots)
    np.save('trueclass.npy',labels)
    np.save('predclass.npy',vclass)

if __name__ == '__main__':
    validate()


