# @DisplayService d
# @double exponent
#
# Demo of manipulating an image using Numpy
# Only works on B/W images (but the arrays that
# are captured and witten back can be N-D)
#
import javabridge as J
import numpy as np

idc = J.class_for_name("net.imagej.display.ImageDisplay")
display = J.run_script("d.getActiveDisplay(idc)", dict(d=d, idc=idc))
data = J.run_script("display.getActiveView().getData()", dict(display=display))
imgplus = J.run_script("data.getImgPlus()", dict(data=data))
ndims = J.run_script("imgplus.numDimensions()", dict(imgplus=imgplus))
start = [J.run_script("java.lang.Long(imgplus.min(i)).intValue();", dict(imgplus=imgplus, i=i)) for i in range(ndims)]
end = [J.run_script("java.lang.Long(imgplus.max(i)).intValue();", dict(imgplus=imgplus, i=i))+1 for i in range(ndims)]
dims = np.array(end) - np.array(start)
a = np.zeros(np.prod(dims), np.float64)
ja = J.get_env().make_double_array(np.ascontiguousarray(a))
strides = np.ones(len(dims), int)
for i in range(0, len(dims)-1):
    strides[-i-2] = strides[-i-1] * dims[-i-1]

J.static_call("net/imglib2/util/ImgUtil", "copy", 
              "(Lnet/imglib2/img/Img;[DI[I)V",
              imgplus, ja, 0, strides)
a = J.get_env().get_double_array_elements(ja)
a.shape = dims
#
# OK now apply a little amateurish warping.
#
e = J.call(exponent, "doubleValue", "()D")
i, j = np.mgrid[0:dims[0], 0:dims[1]].astype(float)
ii = np.minimum(dims[0]-1, dims[0] * (i ** e) / (dims[0] ** e)).astype(int)
jj = np.minimum(dims[1]-1, dims[1] * (j ** e) / (dims[1] ** e)).astype(int)
b = a[ii, jj]
J.static_call("net/imglib2/util/ImgUtil", "copy",
              "([DI[ILnet/imglib2/img/Img;)V",
              b.flatten(), 0, strides, imgplus)
J.call(display, "update", "()V")



