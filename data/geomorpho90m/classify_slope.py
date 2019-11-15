#!/usr/bin/python
# vim: set fileencoding=utf-8 :

"""Process slope tiles from Geomorpho90m into 0.0083 degree pixels."""

import math
import os.path
import sys

import numpy as np
from osgeo import gdal

np.set_printoptions(threshold=sys.maxsize)

outfilename = 'classified_slope_merit_dem_1km_s0..0cm_2018_v1.0.tif'

if not os.path.exists(outfilename):
    modelimg = gdal.Open('../Beck_KG_V1/Beck_KG_V1_present_0p0083.tif', gdal.GA_ReadOnly)
    outxsiz = modelimg.RasterXSize
    outysiz = modelimg.RasterYSize
    drv = gdal.GetDriverByName(modelimg.GetDriver().ShortName)

    out = drv.Create(outfilename, xsize=outxsiz, ysize=outysiz, bands=9, eType=gdal.GDT_Byte,
            options = ['NBITS=7', 'COMPRESS=ZSTD', 'TILED=YES', 'NUM_THREADS=2',
                       'SPARSE_OK=TRUE'])
    out.SetProjection(modelimg.GetProjectionRef())
    out.SetGeoTransform(modelimg.GetGeoTransform())
    out.SetMetadata({
            'TIFFTAG_ARTIST': 'Derived from work by Giuseppe Amatulli (giuseppe.amatulli@gmail.com)',
            'TIFFTAG_DATETIME': '2019',
            'TIFFTAG_IMAGEDESCRIPTION': ('slope classifications, derived from slope geomorpho90m, '
                                         'itself derived from MERIT-DEM')})
    out.GetRasterBand(1).SetNoDataValue(0)
    out = None

out = gdal.Open(outfilename, gdal.GA_Update)
out_xmin, out_xsiz, _, out_ymin, _, out_ysiz = out.GetGeoTransform()

f = open('slope_files.txt', 'r')
for filename in f:
    if filename.strip().startswith('#'):
        print(filename.strip() + " : skipping")
        continue
    print(filename.strip())
    slp = gdal.Open(filename.strip(), gdal.GA_ReadOnly)
    slp_band = slp.GetRasterBand(1)
    slp_x_siz = slp.RasterXSize
    slp_y_siz = slp.RasterYSize
    slp_x_blksiz = slp_y_blksiz = 60

    shape = (int(slp_x_siz/10), int(slp_y_siz/10))
    outband1 = np.empty(shape, dtype=np.uint8)
    outband2 = np.empty(shape, dtype=np.uint8)
    outband3 = np.empty(shape, dtype=np.uint8)
    outband4 = np.empty(shape, dtype=np.uint8)
    outband5 = np.empty(shape, dtype=np.uint8)
    outband6 = np.empty(shape, dtype=np.uint8)
    outband7 = np.empty(shape, dtype=np.uint8)
    outband8 = np.empty(shape, dtype=np.uint8)
    outband9 = np.empty(shape, dtype=np.uint8)

    for slp_y in range(0, slp_y_siz, slp_y_blksiz):
        for slp_x in range(0, slp_x_siz, slp_x_blksiz):
            data = slp_band.ReadAsArray(slp_x, slp_y, slp_x_blksiz, slp_y_blksiz)
            for n in range(slp_y, slp_y+slp_y_blksiz, 10):
                out_y = int(n / 10)
                p_y = int(n - slp_y)
                for m in range(slp_x, slp_x+slp_x_blksiz, 10):
                    out_x = int(m / 10)
                    p_x = int(m - slp_x)
                    p = data[p_x:p_x+10, p_y:p_y+10]  # ~1km² at equator
                    outband1[out_y, out_x] = np.sum(np.logical_and(p >= 0.0, p < 0.5))
                    outband2[out_y, out_x] = np.sum(np.logical_and(p >= 0.5, p < 2.0))
                    outband3[out_y, out_x] = np.sum(np.logical_and(p >= 2.0, p < 5.0))
                    outband4[out_y, out_x] = np.sum(np.logical_and(p >= 5.0, p < 8.0))
                    outband5[out_y, out_x] = np.sum(np.logical_and(p >= 8.0, p < 15.0))
                    outband6[out_y, out_x] = np.sum(np.logical_and(p >= 15.0, p < 30.0))
                    outband7[out_y, out_x] = np.sum(np.logical_and(p >= 30.0, p < 45.0))
                    outband8[out_y, out_x] = np.sum(np.logical_and(p >= 45.0, p <= 90.0))
                    valid = p[np.logical_and(p >= 0.0, p <= 90.0)]
                    if valid.size > 0:
                        outband9[out_y, out_x] = math.floor(np.nanmean(valid))
                    else:
                        outband9[out_y, out_x] = 127

    slp_xmin, _, _, slp_ymin, _, _ = slp.GetGeoTransform()
    out_x = int((slp_xmin - out_xmin) / out_xsiz)
    out_y = int((slp_ymin - out_ymin) / out_ysiz)

    out.GetRasterBand(1).WriteArray(outband1, xoff=out_x, yoff=out_y)
    out.GetRasterBand(2).WriteArray(outband2, xoff=out_x, yoff=out_y)
    out.GetRasterBand(3).WriteArray(outband3, xoff=out_x, yoff=out_y)
    out.GetRasterBand(4).WriteArray(outband4, xoff=out_x, yoff=out_y)
    out.GetRasterBand(5).WriteArray(outband5, xoff=out_x, yoff=out_y)
    out.GetRasterBand(6).WriteArray(outband6, xoff=out_x, yoff=out_y)
    out.GetRasterBand(7).WriteArray(outband7, xoff=out_x, yoff=out_y)
    out.GetRasterBand(8).WriteArray(outband8, xoff=out_x, yoff=out_y)
    out.GetRasterBand(9).WriteArray(outband9, xoff=out_x, yoff=out_y)

out = None
