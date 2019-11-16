The workability_FAO_sq7_1km.tif file was generated from the sq7 ASC file provided by the FAO at:
http://www.fao.org/soils-portal/soil-survey/soil-maps-and-databases/harmonized-world-soil-database-v12/en/

The TIFF version was generated using:

gdal_translate -ot Byte \
	-mo "TIFFTAG_IMAGEDESCRIPTION=Workability raster file, derived from FAO sq7.asc" \
	-mo "TIFFTAG_DATETIME=24 Sep 2019" \
	-a_srs EPSG:4326 -outsize 1000% 0 -co TILED=YES -co COMPRESS=ZSTD -co NBITS=4 \
	./sq7.asc ./workability_FAO_sq7_1km.tif

Note that the original ASCI raster is at ~10km resolution, while we expand this to 1km pixels
in order to work with the extract_country_data.py pipeline.


In addition, a test_small.tif file is generated to use in unit tests:
gdal_translate -outsize 720 0 data/FAO/workability_FAO_sq7_1km.tif data/FAO/test_small.tif

---------------------

The GloSlopesCl*_30as.tif files were generated from ASC raster files downloaded from
http://webarchive.iiasa.ac.at/Research/LUC/External-World-soil-database/HTML/global-terrain-slope-download.html?sb=7
GloSlopesCl1_30as.rar through GloSlopesCl8_30as.rar

gdal_translate -ot Byte -a_srs EPSG:4326 -co COMPRESS=DEFLATE ./GloSlopesCl1_30as.asc ./GloSlopesCl1_30as.tif
gdal_translate -ot Byte -a_srs EPSG:4326 -co COMPRESS=DEFLATE ./GloSlopesCl2_30as.asc ./GloSlopesCl2_30as.tif
gdal_translate -ot Byte -a_srs EPSG:4326 -co COMPRESS=DEFLATE ./GloSlopesCl3_30as.asc ./GloSlopesCl3_30as.tif
gdal_translate -ot Byte -a_srs EPSG:4326 -co COMPRESS=DEFLATE ./GloSlopesCl4_30as.asc ./GloSlopesCl4_30as.tif
gdal_translate -ot Byte -a_srs EPSG:4326 -co COMPRESS=DEFLATE ./GloSlopesCl5_30as.asc ./GloSlopesCl5_30as.tif
gdal_translate -ot Byte -a_srs EPSG:4326 -co COMPRESS=DEFLATE ./GloSlopesCl6_30as.asc ./GloSlopesCl6_30as.tif
gdal_translate -ot Byte -a_srs EPSG:4326 -co COMPRESS=DEFLATE ./GloSlopesCl7_30as.asc ./GloSlopesCl7_30as.tif
gdal_translate -ot Byte -a_srs EPSG:4326 -co COMPRESS=DEFLATE ./GloSlopesCl8_30as.asc ./GloSlopesCl8_30as.tif

gdalbuildvrt -separate GloSlopes.vrt GloSlopesCl1_30as.asc GloSlopesCl2_30as.asc GloSlopesCl3_30as.asc \
    GloSlopesCl4_30as.asc GloSlopesCl5_30as.asc GloSlopesCl6_30as.asc GloSlopesCl7_30as.asc GloSlopesCl8_30as.asc
gdal_translate -ot Byte -a_srs EPSG:4326 -co COMPRESS=ZSTD -co TILED=YES GloSlopes.vrt GloSlopes.tif
