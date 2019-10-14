classified_slope_merit_dem_1km_s0..0cm_2018_v1.0.tif is the result of running
classify_slope.py on the series of gz files in ./slope_files.txt as downloaded
from https://drive.google.com/drive/folders/1FpYxclsvcH0Fq4xMPAFAhZWrN2xqDXFX
Note that the tar.gz files must be unpacked from the shell, attempting to use
/vsitar to access the TIFF files within the archive fails for ~10 of the tarfiles.

The Geomorpho90m paper can be found at https://peerj.com/preprints/27595.pdf


test_small.tif was generated for unit tests using:
gdal_translate -outsize 720 0 data/geomorpho90m/classified_slope_merit_dem_1km_s0..0cm_2018_v1.0.tif data/geomorpho90m/test_small.tif
