import time
import tensorflow as tf
import numpy as np
from PIL import Image
from SpatialTransformer_modify_work.interpolate.bicubic_interp import bicubic_interp_2d


def main():
    img = Image.open(r"C:\Users\anonymous\Desktop\1\lozman.png").convert(mode='RGB').resize([8, 8])
    img.save("d.png")
    img_arr = np.array(img)
    img_tsr = tf.reshape(tf.Variable(img_arr, dtype=tf.float32), [1, 8, 8, 3])
    img_tsr = tf.tile(img_tsr, [32, 1, 1, 1])

    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())
        output = bicubic_interp_2d(img_tsr, (128, 128))
        # output = tf.image.resize_bicubic(img_tsr, [128, 128])
        r = sess.run(output)[0, :, :, :]
        r = np.clip(r, 0, 255).astype(np.uint8)
        print(r)
        Image.fromarray(r).save(r"C:\Users\anonymous\Desktop\1\lozman_interp.png")


if __name__ == '__main__':
    start_time = time.time()
    main()
    print("time elapsed: {}s".format(time.time() - start_time))
