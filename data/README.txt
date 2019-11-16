ConsolidatedSlope.tif uses the FAO slope data in data/FAO for the region 60°N to 60°S.
Beyond 60° FAO has no data, so we use data/geomorpho90m to fill in.

ConsolidatedSlope.tif was produced using the following commands:
	gdal_translate -projwin -180 60 180 -60 -b 1 -b 2 -b 3 -b 4 -b 5 -b 6 -b 7 -b 8 \
                ./FAO/GloSlopes.tif ./FAOslope.tif
	gdal_translate -projwin -180 90 180 60 -b 1 -b 2 -b 3 -b 4 -b 5 -b 6 -b 7 -b 8 \
                ./geomorpho90m/classified_slope_merit_dem_1km_s0..0cm_2018_v1.0.tif ./geomorphoN.tif
	gdal_translate -projwin -180 -60 180 -90  -b 1 -b 2 -b 3 -b 4 -b 5 -b 6 -b 7 -b 8 \
                ./geomorpho90m/classified_slope_merit_dem_1km_s0..0cm_2018_v1.0.tif ./geomorphoS.tif
	gdalbuildvrt temp.vrt geomorphoS.tif FAOslope.tif geomorphoN.tif
	gdal_translate -of GTiff -co COMPRESS=ZSTD -co TILED=YES temp.vrt ./ConsolidatedSlope.tif

A note about TIFF Bands:
When processing the geomorpho slope data we initially created a 9th band, which was an average
slope for the pixel. Later we enhanced process_imagery.py to no longer need this. gdalbuildvrt
cannot combine images with differing numbers of bands, so we explicitly include only the bands
for the 8 slope classes:
    C1: 0%   ≤ slope < 0.5%
    C2: 0.5% ≤ slope < 2%
    C3: 2%   ≤ slope < 5%
    C4: 5%   ≤ slope < 8%
    C5: 8%   ≤ slope < 15%
    C6: 15%  ≤ slope < 30%
    C7: 30%  ≤ slope < 45%
    C8: ≥ 45%
