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

  gdal_rasterize -burn 255 -co tiled=yes -co COMPRESS=DEFLATE -ts 43200 21600 lpd_int2.sqlite -l exploded lpd_int2.tif

Only the resulting GeoTIFF file is checked in here, the original shapefile
can be downloaded from the "Decreasing Land Productivity" section of
https://wad.jrc.ec.europa.eu/geoportal
