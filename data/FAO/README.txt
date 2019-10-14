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
