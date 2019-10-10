classified_slope_merit_dem_1km_s0..0cm_2018_v1.0.tif is the result of running
classify_slope.py on the series of tar.gz files in ./slope_files.txt as downloaded
from https://drive.google.com/drive/folders/1FpYxclsvcH0Fq4xMPAFAhZWrN2xqDXFX

The Geomorpho90m paper can be found at https://peerj.com/preprints/27595.pdf


test_small.tif was generated for unit tests using:
gdalwarp -ts 864 0 ./classified_slope_merit_dem_250m_s0..0cm_2018_v1.0.tif ./test_small.tif
