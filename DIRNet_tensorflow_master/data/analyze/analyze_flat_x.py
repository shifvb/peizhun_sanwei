import os
from matplotlib import pyplot as plt
import numpy as np
import pickle
from pprint import pprint

workspace = r'F:\registration_running_data\temp_variables'
os.chdir(workspace)
filenames = os.listdir(workspace)
arrs = []
for i, filename in enumerate(filenames):
    if i % 10 == 0:
        arr0 = pickle.load(open(filename, 'rb'))[0][1]
        arr0 = arr0.reshape([10, 128, 128])
        # _arr = arr0[0, ::25, ::25]
        # del arr0
        # print(arr0)
        pass
    # arrs.append(arr0)

plt.show()