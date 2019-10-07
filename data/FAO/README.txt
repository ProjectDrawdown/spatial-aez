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

------------

The glc_shv10_dominant_landcover.tif came from
http://www.fao.org/geonetwork/srv/en/main.home?uuid=ba4526fd-cdbf-4028-a1bd-5a559c4bff38
with processing to change the block size to 256x256:

gdal_translate -a_srs EPSG:4326 -co COMPRESS=LZW -co TILED=YES \
	/vsizip/data/FAO/GlcShare_v10_Dominant.zip/glc_shv10_DOM.Tif \
	./data/FAO/glc_shv10_dominant_landcover.tif

Many thanks to user2856 on gis.stackexchange.com for answering:
https://gis.stackexchange.com/questions/337483/gdalwarp-to-change-block-size-also-changes-pixel-values
