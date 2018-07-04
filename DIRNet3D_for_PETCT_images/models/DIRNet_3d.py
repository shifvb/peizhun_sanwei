import os
import pickle
import tensorflow as tf
from tensorflow.contrib.layers import batch_norm
from DIRNet3D_for_PETCT_images.models.SpatialTransformer_3d import SpatialTransformer3D
from DIRNet3D_for_PETCT_images.models.grad_regularization_loss_3d import grad_xyz
from DIRNet3D_for_PETCT_images.models.ncc_loss_3d import ncc


class DIRNet3D(object):
    def __init__(self, img_shape: list, sess: tf.Session, is_train: bool, learning_rate=1e-4):
        """
        construct DIRNet3D
        :param img_shape: 1-D list of
            [batch_size, img_height, img_width, img_depth, img_channels]
        :param sess: current TensorFlow session reference
        :param is_train: bool value to indicate whether it is used for training
        :param learning_rate: learning rate, default to 0.0001
        """
        self.sess = sess

        # declare moving & fixed img placeholder
        self.x = tf.placeholder(dtype=tf.float32, shape=img_shape)
        self.y = tf.placeholder(dtype=tf.float32, shape=img_shape)
        self.xy = tf.concat([self.x, self.y], axis=4)  # concatenate along channel axis

        # get deformation field vector throughout vector CNN
        self.vCNN = _CNN(is_train=is_train, name="vCNN")
        self.def_vec = self.vCNN(tf.transpose(self.xy, perm=[0, 3, 1, 2, 4]))
        self.def_vec = tf.transpose(self.def_vec, perm=[0, 2, 3, 1, 4])

        # get registered image throughout SpatialTransformer
        self.spatial_transformer = SpatialTransformer3D()
        self.z = self.spatial_transformer.transform(self.x, self.def_vec)

        # declare loss
        self.grad_loss = grad_xyz(self.def_vec)
        self.ncc_loss = -ncc(self.y, self.z)
        self.loss = self.ncc_loss + self.grad_loss * 1e-3

        # if train, declare optimizer
        if is_train:
            optimizer = tf.train.AdamOptimizer(learning_rate)
            self.train_step = optimizer.minimize(self.loss, var_list=self.vCNN.var_list)

    def save(self, save_dir):
        self.vCNN.save(self.sess, os.path.join(save_dir, "model.checkpoint"))

    def load(self, load_dir):
        self.vCNN.restore(self.sess, os.path.join(load_dir, "model.checkpoint"))

    def fit(self, batch_x, batch_y):
        # train & calculate loss
        _, loss, ncc_loss, grad_loss = self.sess.run(
            fetches=[self.train_step, self.loss, self.ncc_loss, self.grad_loss],
            feed_dict={self.x: batch_x, self.y: batch_y}
        )
        # return loss
        return loss, ncc_loss, grad_loss

    def deploy(self, batch_x, batch_y, img_path, img_name_start_idx=0, def_vec_path=None):
        # calculate registration result & loss
        z, loss, ncc_loss, grad_loss = self.sess.run(
            fetches=[self.z, self.loss, self.ncc_loss, self.grad_loss],
            feed_dict={self.x: batch_x, self.y: batch_y}
        )
        # save deformation field matrix if `def_vec_path` is set
        if def_vec_path is not None:
            pickle.dump(
                obj=self.sess.run(self.def_vec, {self.x: batch_x, self.y: batch_y}),
                file=open(def_vec_path, 'wb')
            )
        # save image if `img_path` is set
        if img_path is not None:
            for i in range(z.shape[0]):
                _idx = img_name_start_idx + i
                pickle.dump(
                    obj=batch_x[i, :, :, :, 0],
                    file=open(os.path.join(img_path, "{}_x.pickle".format(_idx)), 'wb')
                )
                pickle.dump(
                    obj=batch_y[i, :, :, :, 0],
                    file=open(os.path.join(img_path, "{}_y.pickle".format(_idx)), 'wb')
                )
                pickle.dump(
                    obj=z[i, :, :, :, 0],
                    file=open(os.path.join(img_path, "{}_z.pickle".format(_idx)), 'wb')
                )

        # return loss
        return loss, ncc_loss, grad_loss


class _CNN(object):
    def __init__(self, is_train, name):
        self.name = name
        self.is_train = is_train
        self.reuse = None

    def __call__(self, x):
        """
        :param x: Shape `[batch, in_depth, in_height, in_width, in_channels]`
        """
        with tf.variable_scope(self.name, reuse=self.reuse):
            # conv_1
            x = self._conv3d(x, "conv1", 16, 3, 1, "SAME", True, tf.nn.elu, self.is_train)
            # pool_1
            x = tf.nn.avg_pool3d(x, [1, 2, 2, 2, 1], [1, 2, 2, 2, 1], "SAME")
            # conv_2
            x = self._conv3d(x, "conv2", 16, 3, 1, "SAME", True, tf.nn.elu, self.is_train)
            # pool_2
            x = tf.nn.avg_pool3d(x, [1, 2, 2, 2, 1], [1, 2, 2, 2, 1], "SAME")
            # conv_3
            x = self._conv3d(x, "conv3", 16, 3, 1, "SAME", True, tf.nn.elu, self.is_train)
            # pool_3
            x = tf.nn.avg_pool3d(x, [1, 2, 2, 2, 1], [1, 2, 2, 2, 1], "SAME")
            # conv_4
            x = self._conv3d(x, "conv4", 16, 3, 1, "SAME", True, tf.nn.elu, self.is_train)
            # pool_4
            x = tf.nn.avg_pool3d(x, [1, 2, 2, 2, 1], [1, 2, 2, 2, 1], "SAME")
            # conv_5
            x = self._conv3d(x, "conv5", 16, 1, 1, "SAME", True, tf.nn.elu, self.is_train)
            # conv_6
            x = self._conv3d(x, "conv6", 16, 1, 1, "SAME", True, tf.nn.elu, self.is_train)
            # conv_7
            x = self._conv3d(x, "conv7", 2, 1, 1, "SAME", False, None, self.is_train)

        if self.reuse is None:
            self.var_list = tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope=self.name)
            self.saver = tf.train.Saver(self.var_list)
            self.reuse = True

        return x

    def save(self, sess, path):
        self.saver.save(sess, path)

    def restore(self, sess, path):
        self.saver.restore(sess, path)

    @classmethod
    def _conv3d(cls, x, name, kernel_num, kernel_size, strides, padding, batch_normal, active_function, is_train):
        with tf.variable_scope(name):
            # convolution 3d
            w = tf.get_variable('w', shape=[kernel_size, kernel_size, kernel_size, x.shape[-1], kernel_num],
                                initializer=tf.truncated_normal(stddev=0.01))
            x = tf.nn.conv3d(x, w, [1, strides, strides, strides, 1], padding)
            # batch normal
            if batch_normal:
                x = cls._batch_norm(x, "bn", is_train=is_train)
            else:
                b = tf.get_variable('b', [kernel_num], initializer=tf.constant_initializer(0.))
                x += b

            # active function
            if active_function:
                x = active_function(x)

        return x

    @classmethod
    def _batch_norm(cls, x, name, momentum=0.9, epsilon=1e-5, is_train=True):
        return batch_norm(x, decay=momentum, updates_collections=None,
                          epsilon=epsilon, scale=True, is_training=is_train, scope=name)
