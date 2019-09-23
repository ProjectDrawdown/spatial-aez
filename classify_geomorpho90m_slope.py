import numpy as np
from osgeo import gdal

filename = 'data/geomorpho90m/dtm_slope_merit.dem_m_250m_s0..0cm_2018_v1.0.tif'
outfile = 'data/geomorpho90m/classified_slope_merit_dem_250m_s0..0cm_2018_v1.0.tif'

img = gdal.Open(filename, gdal.GA_ReadOnly)
xsiz = img.RasterXSize
ysiz = img.RasterYSize
drv = gdal.GetDriverByName(img.GetDriver().ShortName)
band = img.GetRasterBand(1)

out = drv.Create(outfile, xsiz, ysiz, 1, gdal.GDT_Byte, options = ['COMPRESS=LZW'])
out.SetProjection(img.GetProjectionRef())
out.SetGeoTransform(img.GetGeoTransform())
out.SetMetadata({'Offset':'0', 'Scale': '0.01',
                 'TIFFTAG_ARTIST': 'Derived from work by Giuseppe Amatulli (giuseppe.amatulli@gmail.com)',
                 'TIFFTAG_DATETIME': '2019',
                 'TIFFTAG_IMAGEDESCRIPTION': 'GAEZ 3.0 classifications, derived from slope geomorpho90m, itself derived from MERIT-DEM - resolution 3 arc-seconds'})
outband = out.GetRasterBand(1)
outband.SetNoDataValue(255)

for yoff in range(0, ysiz):
    if yoff > 0 and (yoff % (ysiz / 100)) == 0:
        print(f'{yoff}/{ysiz}')
    data = band.ReadAsArray(0, yoff, xsiz, 1)

    data[np.logical_and(data >= 0, data < 50)] = 0
    data[np.logical_and(data >= 50, data < 200)] = 1
    data[np.logical_and(data >= 200, data < 500)] = 2
    data[np.logical_and(data >= 500, data < 800)] = 3
    data[np.logical_and(data >= 800, data < 1600)] = 4
    data[np.logical_and(data >= 1600, data < 3000)] = 5
    data[np.logical_and(data >= 3000, data < 4500)] = 6
    data[data >= 4500] = 7
    data[data < 0] = 255

    outband.WriteArray(data, 0, yoff)

out = None
del outband
