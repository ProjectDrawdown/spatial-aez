import glob
import tarfile

import numpy as np
from osgeo import gdal

modelimg = gdal.Open('../Beck_KG_V1/Beck_KG_V1_present_0p0083.tif', gdal.GA_ReadOnly)
outxsiz = modelimg.RasterXSize
outysiz = modelimg.RasterYSize
drv = gdal.GetDriverByName(modelimg.GetDriver().ShortName)

outfilename = 'classified_slope_merit_dem_1km_s0..0cm_2018_v1.0.tif'
out = drv.Create(outfilename, xsize=outxsiz, ysize=outysiz, bands=8, eType=gdal.GDT_Byte,
        options = ['NBITS=7', 'COMPRESS=ZSTD', 'TILED=YES', 'NUM_THREADS=2',
                   'PHOTOMETRIC=MINISBLACK', 'SPARSE_OK=TRUE'])
out.SetProjection(modelimg.GetProjectionRef())
out.SetGeoTransform(modelimg.GetGeoTransform())
out.SetMetadata({
        'TIFFTAG_ARTIST': 'Derived from work by Giuseppe Amatulli (giuseppe.amatulli@gmail.com)',
        'TIFFTAG_DATETIME': '2019',
        'TIFFTAG_IMAGEDESCRIPTION': ('slope classifications, derived from slope geomorpho90m, '
                                     'itself derived from MERIT-DEM')})
out_xmin, out_xsiz, _, out_ymin, _, out_ysiz = out.GetGeoTransform()
outband = {}
for b in range(1, 9):
    outband[b] = out.GetRasterBand(b)
    outband[b].SetNoDataValue(0)
modelimg = None

f = open('slope_files.txt', 'r')
for filename in f:
    print(filename.strip())
    slp = gdal.Open(filename.strip(), gdal.GA_ReadOnly)
    slp_xmin, slp_xsiz, _, slp_ymin, _, slp_ysiz = slp.GetGeoTransform()
    out_x_initial = int((slp_xmin - out_xmin) / out_xsiz)
    out_y = int((slp_ymin - out_ymin) / out_ysiz)
    slp_band = slp.GetRasterBand(1)
    slp_x_siz = slp.RasterXSize
    slp_y_siz = slp.RasterYSize
    slp_x_blksiz = slp_y_blksiz = 10

    for slp_y in range(0, slp_y_siz, slp_y_blksiz):
        out_x = out_x_initial
        for slp_x in range(0, slp_x_siz, slp_x_blksiz):
            data = slp_band.ReadAsArray(slp_x, slp_y, slp_x_blksiz, slp_y_blksiz)
            c1 = np.array([[np.sum(np.logical_and(data >= 0, data < 50))]], dtype=np.uint8)
            outband[1].WriteArray(c1, xoff=out_x, yoff=out_y)
            c2 = np.array([[np.sum(np.logical_and(data >= 50, data < 200))]], dtype=np.uint8)
            outband[2].WriteArray(c2, xoff=out_x, yoff=out_y)
            c3 = np.array([[np.sum(np.logical_and(data >= 200, data < 500))]], dtype=np.uint8)
            outband[3].WriteArray(c3, xoff=out_x, yoff=out_y)
            c4 = np.array([[np.sum(np.logical_and(data >= 500, data < 800))]], dtype=np.uint8)
            outband[4].WriteArray(c4, xoff=out_x, yoff=out_y)
            c5 = np.array([[np.sum(np.logical_and(data >= 800, data < 1600))]], dtype=np.uint8)
            outband[5].WriteArray(c5, xoff=out_x, yoff=out_y)
            c6 = np.array([[np.sum(np.logical_and(data >= 1600, data < 3000))]], dtype=np.uint8)
            outband[6].WriteArray(c6, xoff=out_x, yoff=out_y)
            c7 = np.array([[np.sum(np.logical_and(data >= 3000, data < 4500))]], dtype=np.uint8)
            outband[7].WriteArray(c7, xoff=out_x, yoff=out_y)
            c8 = np.array([[np.sum(data >= 4500)]])
            outband[8].WriteArray(c8, xoff=out_x, yoff=out_y)
            out_x += 1
        out_y += 1

for b in range(1, 9):
    outband[b] = None
out = None
