The workability_FAO_sq7_10km.tif file was generated from the sq7 ASC file provided by the FAO at:
http://www.fao.org/soils-portal/soil-survey/soil-maps-and-databases/harmonized-world-soil-database-v12/en/

The TIFF version was generated using:

gdal_translate -ot Byte \
	-mo "TIFFTAG_IMAGEDESCRIPTION=Workability raster file, derived from FAO sq7.asc" \
	-mo "TIFFTAG_DATETIME=24 Sep 2019" \
	-a_srs EPSG:4326 \
	./sq7.asc ./workability_FAO_sq7_10km.tif

Note that while one may be tempted to add compression options, doing so results in
reshuffling the pixel color values (for better compression) and makes it so we cannot
easily process the file. With 10km resolution, the GeoTIFF file is relatively small
even without compression.
