
# coding: utf-8

'''
This file contains different models, including our baseline: MotifGCN and our mutant: MotifAttGCN.
MotifGCN:
    convolution layer + convolution layer + fully connected layer + fully connected layer + fully connected layer
MotifAttGCN:
    convolution layer + convolution layer + attention layer + ensemble layer

hid_units, n_heads, residual, nonlinearity are attention layer's hyperparameters.

Created by GongQiran on 18/8/4.
Copyright 2018 GongQiran. All rights reserved.

'''

import tensorflow as tf
import layers

# attention
hid_units = [16]
n_heads = [8,1]
residual = False
nonlinearity = tf.nn.elu
attention_model = layers.GAT()

class MotifAttGCN(object):
    def __init__(self, session, 
                 batch_size,
                 class_size,
                 seq_len,
                 order_len,
                 conv1_ksize=3, 
                 conv1_output_channels=32,
                 conv2_ksize=3, 
                 conv2_output_channels=64,
                 dropout_ratio=0.5,
                 k = 3):
        self.batch_size = batch_size
        self.class_size = class_size
        self.seq_len = seq_len
        self.order_len = order_len
        self.conv1_ksize = conv1_ksize
        self.conv1_output_channels = conv1_output_channels
        self.conv2_ksize = conv2_ksize
        self.conv2_output_channels = conv2_output_channels
        self.dropout_ratio = dropout_ratio
        self.k = k
        
        self.build_placeholders()
        
        self.loss, self.probabilities = self.forward_propagation()
        self.l2 = tf.contrib.layers.apply_regularization(tf.contrib.layers.l2_regularizer(0.01), tf.trainable_variables())
        self.pred = tf.to_int32(tf.argmax(self.probabilities, 1))
        correct_prediction = tf.equal(self.pred, self.t)
        self.accuracy = tf.reduce_mean(tf.cast(correct_prediction, "float"))
        print('Forward propagation finished.')
        
        self.sess = session
        self.optimizer = tf.train.MomentumOptimizer(self.lr, self.mom).minimize((self.loss+self.l2))
        self.init = tf.global_variables_initializer()
        self.saver = tf.train.Saver(tf.global_variables())
        print('Backward propagation finished.')
        
    def build_placeholders(self):
        self.x = tf.placeholder(tf.float32, [None, self.order_len, self.seq_len*self.k], 'graph_nodes')
        self.t = tf.placeholder(tf.int32, [None], 'labels')
        self.lr = tf.placeholder(tf.float32, [], 'learning_rate')
        self.mom = tf.placeholder(tf.float32, [], 'momentum')
        
    def forward_propagation(self):
        with tf.variable_scope('conv_n1'):
            x = tf.expand_dims(self.x, -1)
            conv1 = tf.layers.conv2d(
                inputs=x,
                filters=self.conv1_output_channels,
                kernel_size=[1, self.conv1_ksize],
                strides=(1, self.k),
                padding="valid",
                activation=tf.nn.relu)

            dropout1 = tf.layers.dropout(
                inputs=conv1, rate=self.dropout_ratio)
    
        with tf.variable_scope('conv_n2'):
            conv2 = tf.layers.conv2d(
                inputs=dropout1,
                filters=self.conv2_output_channels,
                kernel_size=[self.conv2_ksize, 1],
                strides=(3, 1),
                padding="valid",
                activation=tf.nn.relu)

            dropout2 = tf.layers.dropout(
                inputs=conv2, rate=self.dropout_ratio)

        # (batch_size, feature_len, seq_len, filters)
        with tf.variable_scope('attention_n'):
            dropout2_trans = tf.transpose(dropout2, [0, 3, 1, 2])
            # (batch_size, filters, feature_len, seq_len)
            dropout2_re = tf.reshape(dropout2_trans, [-1, dropout2.shape[3]*dropout2.shape[1], dropout2.shape[2]])
            dropout2_re = tf.transpose(dropout2_re, [0, 2, 1])  
            # add attention layers
            # input size == dropout2_re size ==> (batch_size, feature_len*filters, seq_len)
            # output size should be (batch_size, class_size, seq_len)
            attention_output = attention_model.inference(dropout2_re,self.class_size,0,hid_units,n_heads,residual,nonlinearity)
            # (batch_size, node_len, class)
        
        with tf.variable_scope('ensemble_n'):
            soft_layer = tf.nn.softmax(attention_output, axis=2)
            vote_layer = tf.reduce_sum(soft_layer, axis=1)
            # vote_layer size should be (batch_size, class_size)
            loss = tf.losses.sparse_softmax_cross_entropy(labels=self.t, logits=vote_layer)
        
        return loss, tf.nn.softmax(vote_layer, name="probabilities")
    
    def train(self, batch_x, batch_t, learning_rate = 1e-3, momentum = 0.9):
        feed_dict = {
            self.x : batch_x,
            self.t : batch_t, 
            self.lr: learning_rate,
            self.mom: momentum
        }
        _, loss, acc, pred = self.sess.run([self.optimizer, self.loss, self.accuracy, self.pred], feed_dict = feed_dict)
        
        return loss, acc, pred
    
    def evaluate(self, batch_x, batch_t):
        feed_dict = {
            self.x : batch_x,
            self.t : batch_t
        }
        acc, pred = self.sess.run([self.accuracy, self.pred], feed_dict = feed_dict)
        
        return acc, pred

class MotifGCN(object):
    def __init__(self, session, 
                 batch_size,
                 class_size,
                 seq_len,
                 order_len,
                 conv1_ksize=3, 
                 conv1_output_channels=32,
                 conv2_ksize=3, 
                 conv2_output_channels=64,
                 dropout_ratio=0.5,
                 fc1_output_size=128,
                 fc2_output_size=64,
                 k = 3):
        self.batch_size = batch_size
        self.class_size = class_size
        self.seq_len = seq_len
        self.order_len = order_len
        self.conv1_ksize = conv1_ksize
        self.conv1_output_channels = conv1_output_channels
        self.conv2_ksize = conv2_ksize
        self.conv2_output_channels = conv2_output_channels
        self.dropout_ratio = dropout_ratio
        self.fc1_output_size = fc1_output_size
        self.fc2_output_size = fc2_output_size
        self.k = k
        
        self.build_placeholders()
        
        self.loss, self.probabilities = self.forward_propagation()
        self.pred = tf.to_int32(tf.argmax(self.probabilities, 1))
        correct_prediction = tf.equal(self.pred, self.t)
        self.accuracy = tf.reduce_mean(tf.cast(correct_prediction, "float"))
        print('Forward propagation finished.')
        
        self.sess = session
        self.optimizer = tf.train.MomentumOptimizer(self.lr, self.mom).minimize(self.loss)
        self.init = tf.global_variables_initializer()
        self.saver = tf.train.Saver(tf.global_variables())
        print('Backward propagation finished.')
        
    def build_placeholders(self):
        self.x = tf.placeholder(tf.float32, [None, self.order_len, self.seq_len*self.k], 'graph_nodes')
        self.t = tf.placeholder(tf.int32, [None], 'labels')
        self.lr = tf.placeholder(tf.float32, [], 'learning_rate')
        self.mom = tf.placeholder(tf.float32, [], 'momentum')
        
    def forward_propagation(self):
        with tf.variable_scope('conv_n1'):
            x = tf.expand_dims(self.x, -1)
            conv1 = tf.layers.conv2d(
                inputs=x,
                filters=self.conv1_output_channels,
                kernel_size=[1, self.conv1_ksize],
                strides=(1, self.k),
                padding="valid",
                activation=tf.nn.relu)

            dropout1 = tf.layers.dropout(
                inputs=conv1, rate=self.dropout_ratio)
    
        with tf.variable_scope('conv_n2'):
            conv2 = tf.layers.conv2d(
                inputs=dropout1,
                filters=self.conv2_output_channels,
                kernel_size=[self.conv2_ksize, 1],
                strides=(3, 1),
                padding="valid",
                activation=tf.nn.relu)

            dropout2 = tf.layers.dropout(
                inputs=conv2, rate=self.dropout_ratio)

        # (batch_size, feature_len, seq_len, filters)
        with tf.variable_scope('fc_n'):
            flat = tf.reshape(dropout2, [-1, dropout2.shape[1]*dropout2.shape[2]*dropout2.shape[3]])
            dense1 = tf.layers.dense(inputs=flat, units=self.fc1_output_size, activation=tf.nn.relu)
            dense2 = tf.layers.dense(inputs=dense1, units=self.fc2_output_size, activation=tf.nn.relu)
            dense3 = tf.layers.dense(inputs=dense2, units=self.class_size, activation=None)

            loss = tf.losses.sparse_softmax_cross_entropy(labels=self.t, logits=dense3)
        
        return loss, tf.nn.softmax(dense3, name="probabilities")
    
    def train(self, batch_x, batch_t, learning_rate = 1e-3, momentum = 0.9):
        feed_dict = {
            self.x : batch_x,
            self.t : batch_t, 
            self.lr: learning_rate,
            self.mom: momentum
        }
        _, loss, acc, pred = self.sess.run([self.optimizer, self.loss, self.accuracy, self.pred], feed_dict = feed_dict)
        
        return loss, acc, pred
    
    def evaluate(self, batch_x, batch_t):
        feed_dict = {
            self.x : batch_x,
            self.t : batch_t
        }
        acc, pred = self.sess.run([self.accuracy, self.pred], feed_dict = feed_dict)
        
        return acc, pred



