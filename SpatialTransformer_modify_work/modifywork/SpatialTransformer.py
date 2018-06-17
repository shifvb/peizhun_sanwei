import tensorflow as tf
from SpatialTransformer_modify_work.models.bicubic_interp import bicubic_interp_2d


class SpatialTransformer(object):
    """Deformable Transformer Layer with bicubic interpolation
    U : tf.float, [num_batch, height, width, num_channels].
        Input tensor to warp
    V : tf.float, [num_batch, height, width, 2]
        Warp map. It is interpolated to out_size.
    out_size: a tuple of two ints
        The size of the output of the network (height, width)
    ----------
    References :
      https://github.com/daviddao/spatial-transformer-tensorflow/blob/master/spatial_transformer.py
    """

    def __call__(self, U, V):
        # deformation field
        V = bicubic_interp_2d(V, U.shape[1:3])  # [n, h, w, 2]
        dx = V[:, :, :, 0]  # [n, h, w]
        dy = V[:, :, :, 1]  # [n, h, w]
        return self._transform(U, dx, dy)

    def _transform(self, U, dx, dy):
        """
        transform (x, y)^T -> (x+vx, x+vy)^T
        :param U: image
            example: a 256x256 single-channel image
                [batch_size, 256, 256, 1]
        :param V: deformation field
            example: an 8x8 deformation field
                [batch_size, 8, 8, 2]
        :return: registered result
        """
        batch_size = U.shape[0]
        height = U.shape[1]
        width = U.shape[2]

        # grid of (x_t, y_t, 1), eq (1) in ref [1]
        x_mesh, y_mesh = self._meshgrid(height, width)  # [h, w]
        x_mesh = tf.tile(tf.expand_dims(x_mesh, 0), [batch_size, 1, 1])  # [n, h, w]
        y_mesh = tf.tile(tf.expand_dims(y_mesh, 0), [batch_size, 1, 1])  # [n, h, w]

        # Convert dx and dy to absolute locations
        x_new = dx + x_mesh
        y_new = dy + y_mesh

        return self._interpolate(U, x_new, y_new, [height, width])

    def _repeat(self, x, n_repeats):
        rep = tf.transpose(tf.expand_dims(tf.ones(shape=tf.stack([n_repeats, ])), 1), [1, 0])
        rep = tf.cast(rep, dtype='int32')
        x = tf.matmul(tf.reshape(x, (-1, 1)), rep)
        return tf.reshape(x, [-1])

    def _meshgrid(self, height, width):
        # This should be equivalent to:
        #  x_t, y_t = np.meshgrid(np.linspace(-1, 1, width),
        #                         np.linspace(-1, 1, height))
        #  ones = np.ones(np.prod(x_t.shape))
        #  grid = np.vstack([x_t.flatten(), y_t.flatten(), ones])
        x_t = tf.matmul(
            tf.ones(shape=tf.stack([height, 1])),
            tf.transpose(tf.expand_dims(tf.linspace(-1.0, 1.0, width), 1), [1, 0])
        )
        y_t = tf.matmul(
            tf.expand_dims(tf.linspace(-1.0, 1.0, height), 1),
            tf.ones(shape=tf.stack([1, width]))
        )
        return x_t, y_t

    def _interpolate(self, im, x, y, out_size):
        # constants
        num_batch = tf.shape(im)[0]
        height = tf.shape(im)[1]
        width = tf.shape(im)[2]
        channels = tf.shape(im)[3]

        out_height = out_size[0]
        out_width = out_size[1]

        x = tf.reshape(x, [-1])
        y = tf.reshape(y, [-1])

        x = tf.cast(x, 'float32')
        y = tf.cast(y, 'float32')

        height_f = tf.cast(height, 'float32')
        width_f = tf.cast(width, 'float32')

        zero = tf.zeros([], dtype='int32')
        max_y = tf.cast(tf.shape(im)[1] - 1, 'int32')
        max_x = tf.cast(tf.shape(im)[2] - 1, 'int32')

        # scale indices from [-1, 1] to [0, width/height]
        x = (x + 1.0) * (width_f) / 2.0
        y = (y + 1.0) * (height_f) / 2.0

        # do sampling
        x0 = tf.cast(tf.floor(x), 'int32')
        x1 = x0 + 1
        y0 = tf.cast(tf.floor(y), 'int32')
        y1 = y0 + 1

        x0 = tf.clip_by_value(x0, zero, max_x)
        x1 = tf.clip_by_value(x1, zero, max_x)
        y0 = tf.clip_by_value(y0, zero, max_y)
        y1 = tf.clip_by_value(y1, zero, max_y)
        dim2 = width
        dim1 = width * height
        base = self._repeat(tf.range(num_batch) * dim1, out_height * out_width)
        base_y0 = base + y0 * dim2
        base_y1 = base + y1 * dim2
        idx_a = base_y0 + x0
        idx_b = base_y1 + x0
        idx_c = base_y0 + x1
        idx_d = base_y1 + x1

        # use indices to lookup pixels in the flat image and restore
        # channels dim
        im_flat = tf.reshape(im, tf.stack([-1, channels]))
        im_flat = tf.cast(im_flat, 'float32')
        Ia = tf.gather(im_flat, idx_a)
        Ib = tf.gather(im_flat, idx_b)
        Ic = tf.gather(im_flat, idx_c)
        Id = tf.gather(im_flat, idx_d)

        # and finally calculate interpolated values
        x0_f = tf.cast(x0, 'float32')
        x1_f = tf.cast(x1, 'float32')
        y0_f = tf.cast(y0, 'float32')
        y1_f = tf.cast(y1, 'float32')
        wa = tf.expand_dims(((x1_f - x) * (y1_f - y)), 1)
        wb = tf.expand_dims(((x1_f - x) * (y - y0_f)), 1)
        wc = tf.expand_dims(((x - x0_f) * (y1_f - y)), 1)
        wd = tf.expand_dims(((x - x0_f) * (y - y0_f)), 1)

        output = tf.add_n([wa * Ia, wb * Ib, wc * Ic, wd * Id])
        output = tf.reshape(output, [num_batch, height, width, channels])
        return output
