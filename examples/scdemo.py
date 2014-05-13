# @DisplayService d
# @double frequency(min="1")
# @double magnitude(min="1")
#
# Demo of manipulating an image using Numpy
# Only works on B/W images (but the arrays that
# are captured and witten back can be N-D)
#
import javabridge as J
import numpy as np
importClass("net.imagej.display.ImageDisplay")
importClass("net.imglib2.util.ImgUtil")

display = d.getActiveDisplay(ImageDisplay.klass)
data = display.getActiveView().getData()
imgplus = data.getImgPlus()
ndims = imgplus.numDimensions()
start = [imgplus.min(i) for i in range(ndims)]
end = [imgplus.max(i)+1 for i in range(ndims)]
dims = np.array(end) - np.array(start)
a = np.zeros(np.prod(dims), np.float64)
ja = J.get_env().make_double_array(np.ascontiguousarray(a))
strides = np.ones(len(dims), int)
for i in range(0, len(dims)-1):
    strides[-i-2] = strides[-i-1] * dims[-i-1]

ImgUtil.copy(imgplus, ja, 0, strides)
a = J.get_env().get_double_array_elements(ja)
a.shape = dims
#
# OK now apply a little amateurish warping.
#
i, j = np.mgrid[0:dims[0], 0:dims[1]].astype(float)
id = np.sin(2*np.pi * i * frequency / dims[0]) * magnitude
jd = np.sin(2*np.pi * j * frequency / dims[1]) * magnitude
ii = np.maximum(0, np.minimum(dims[0]-1, i+id)).astype(int)
jj = np.maximum(0, np.minimum(dims[1]-1, j+jd)).astype(int)
b = a[ii, jj]
ImgUtil.copy(b.flatten(), 0, strides, imgplus)
display.update()

