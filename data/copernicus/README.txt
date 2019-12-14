GeoTIFF file created from NetCDF downloaded from https://maps.elie.ucl.ac.be/CCI/viewer/download.php using:

gdalwarp -of Gtiff -co COMPRESS=ZSTD -co TILED=YES -ot Byte -te -180.0000000 -90.0000000 180.0000000 90.0000000 -tr 0.002777777777778 0.002777777777778 -t_srs EPSG:4326 NETCDF:C3S-LC-L4-LCCS-Map-300m-P1Y-2018-v2.1.1.nc:lccs_class C3S-LC-L4-LCCS-Map-300m-P1Y-2018-v2.1.1.tif

test_small.tif was created for unit tests, using an earlier version of the land cover data:

gdal_translate -outsize 720 0 data/ucl_elie/ESACCI-LC-L4-LCCS-Map-300m-P1Y-2015-v2.0.7.tif data/ucl_elie/test_small.tif
