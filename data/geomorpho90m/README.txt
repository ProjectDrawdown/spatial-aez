classified_slope_merit_dem_250m_s0..0cm_2018_v1.0.tif is the result of running the
classify_geomorpho90m_slope.py script on dtm_slope_merit.dem_m_250m_s0..0cm_2018_v1.0.tif
as downloaded from https://drive.google.com/drive/folders/1D4YHUycBBhNFVVsz4ohaJI7QXV9BEh94

dtm_slope_merit.dem_m_250m_s0..0cm_2018_v1.0.tif is 5 GBytes, which is too large to
upload to github (which limits even git-lfs files to 2 GBytes).

The Geomorpho90m paper can be found at https://peerj.com/preprints/27595.pdf


test_small.tif was generated for unit tests using:
gdalwarp -ts 864 0 ./classified_slope_merit_dem_250m_s0..0cm_2018_v1.0.tif ./test_small.tif
