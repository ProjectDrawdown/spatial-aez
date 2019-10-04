from osgeo import gdal

modelimg = gdal.Open('../Beck_KG_V1/Beck_KG_V1_present_0p0083.tif', gdal.GA_ReadOnly)
outxsiz = modelimg.RasterXSize
outysiz = modelimg.RasterYSize
drv = gdal.GetDriverByName(modelimg.GetDriver().ShortName)

outfilename = 'classified_slope_merit_dem_1km_s0..0cm_2018_v1.0.tif'
out = drv.Create(outfilename, xsize=outxsiz, ysize=outysiz, bands=8, eType=gdal.GDT_Byte,
        options = ['COMPRESS=ZSTD', 'TILED=YES', 'NUM_THREADS=2'])
out.SetProjection(modelimg.GetProjectionRef())
out.SetGeoTransform(modelimg.GetGeoTransform())
out.SetMetadata({
        'TIFFTAG_ARTIST': 'Derived from work by Giuseppe Amatulli (giuseppe.amatulli@gmail.com)',
        'TIFFTAG_DATETIME': '2019',
        'TIFFTAG_IMAGEDESCRIPTION': ('slope classifications, derived from slope geomorpho90m, '
                                     'itself derived from MERIT-DEM')})
out = None
