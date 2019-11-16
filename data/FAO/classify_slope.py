#!/usr/bin/python
# vim: set fileencoding=utf-8 :

"""Process slope tiles from FAO into a multi-band TIF file."""

import math
import os.path
import sys

import numpy as np
from osgeo import gdal

np.set_printoptions(threshold=sys.maxsize)

outfilename = 'classified_slope_FAO_1km.tif'

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
            'TIFFTAG_ARTIST': 'Derived from the Harmonized World Soil Database',
            'TIFFTAG_DATETIME': '2019',
    out.GetRasterBand(1).SetNoDataValue(0)
    out = None

out = gdal.Open(outfilename, gdal.GA_Update)
out_xmin, out_xsiz, _, out_ymin, _, out_ysiz = out.GetGeoTransform()
out_band = {}
for i in range(1, 10):
    out_band[i] = out.GetRasterBand(i)

in_f = {}
in_f[1] = gdal.Open('GloSlopesCl1_30as.tif', gdal.GA_ReadOnly)
in_f[2] = gdal.Open('GloSlopesCl2_30as.tif', gdal.GA_ReadOnly)
in_f[3] = gdal.Open('GloSlopesCl3_30as.tif', gdal.GA_ReadOnly)
in_f[4] = gdal.Open('GloSlopesCl4_30as.tif', gdal.GA_ReadOnly)
in_f[5] = gdal.Open('GloSlopesCl5_30as.tif', gdal.GA_ReadOnly)
in_f[6] = gdal.Open('GloSlopesCl6_30as.tif', gdal.GA_ReadOnly)
in_f[7] = gdal.Open('GloSlopesCl7_30as.tif', gdal.GA_ReadOnly)
in_f[8] = gdal.Open('GloSlopesCl8_30as.tif', gdal.GA_ReadOnly)

in_band = {}
for i in range(1, 9):
    in_band[i] = in_f[i].GetRasterBand(1)

x_siz = in_f[1].RasterXSize
y_siz = in_f[1].RasterYSize
x_blksiz = y_blksiz = 256

for y in range(0, y_siz, y_blksiz):
    for x in range(0, x_siz, x_blksiz):
        data = {}
        for i in range(1, 9):
            data[i] = in_band[i].ReadAsArray(x, y, x_blksiz, y_blksiz)
            if not np.all(data[i][data == 255]):
                out_band[i].WriteArray(data[i], xoff=x, yoff=y)

out = None
