lpd_int2 dataset regarding soil degradation downloaded from
https://wad.jrc.ec.europa.eu/geoportal (select
"Decreasing Land Productivity") on Oct 25, 2019.

The dataset is supplied as a Shapefile, with one feature per country.
However the multipolygons in the shapefile are extremely complex, with
up to a half million edges. gdal_rasterize does not handle this well,
we gave up after 6 days of letting it try to rasterize the original
shapefile.

Based on this answer by user30184 at https://gis.stackexchange.com/questions/339845/
we simplified the multipolygons:

  ogrinfo ./lpd_int2.sqlite -sql "SELECT ElementaryGeometries('lpd_int2','GEOMETRY','exploded','id_1','id_2');"

Then rasterized the simplified file:

  gdal_rasterize -burn 1 -co TILED=YES -co COMPRESS=DEFLATE -co NBITS=1 -ot Byte \
    -ts 43200 21600 -te -180.0 -90.0 180.0 90.0 lpd_int2.sqlite -l exploded lpd_int2.tif

The arguments are:
  -burn 1 : use a value of 1 for areas inside the shapefile.
  -co TILED=YES : structure the TIF file in 256x256 blocks, which is an efficient size for
        the rest of our processing.
  -co COMPRESS=DEFLATE -co NBITS=1 -ot Byte : produce a TIF with one bit per pixel, and compress it.
  -ts 43200 21600 : produce a TIF of 43200x21600 pixels
  -te -180.0 -90.0 180.0 90.0 : the LPD dataset is 72.4° North to 55.6° South. To speed processing
        we have a set of precomputed country areas in masks/*_1km_mask._tif which are 90° N to S.
        Precomputing the masks speeds processing by about 15x, so we extend this dataset to 90°.
        The extended area contains NoData, which defaults to zero for non-degraded.

Only the resulting GeoTIFF file is checked in here, the original shapefile
can be downloaded from the "Decreasing Land Productivity" section of
https://wad.jrc.ec.europa.eu/geoportal
