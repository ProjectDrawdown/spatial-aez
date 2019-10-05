import numpy as np
from osgeo import gdal

out = gdal.Open('classified_slope_merit_dem_1km_s0..0cm_2018_v1.0.tif', gdal.GA_Update)
out_xmin, out_xsiz, _, out_ymin, _, out_ysiz = out.GetGeoTransform()

f = open('slope_files.txt', 'r')
for filename in f:
    if filename.strip().startswith('#'):
        print(f"{filename.strip()} : skipping")
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

    for slp_y in range(0, slp_y_siz, slp_y_blksiz):
        out_y = int(slp_y / 10)
        for slp_x in range(0, slp_x_siz, slp_x_blksiz):
            data = slp_band.ReadAsArray(slp_x, slp_y, slp_x_blksiz, slp_y_blksiz)
            for m in range(slp_x, slp_x+slp_x_blksiz, 10):
                out_x = int(m / 10)
                mdata = data[m:m+10, slp_y:slp_y+10]
                outband1[out_x, out_y] = np.sum(np.logical_and(mdata >= 0, mdata < 50))
                outband2[out_x, out_y] = np.sum(np.logical_and(mdata >= 50, mdata < 200))
                outband3[out_x, out_y] = np.sum(np.logical_and(mdata >= 200, mdata < 500))
                outband4[out_x, out_y] = np.sum(np.logical_and(mdata >= 500, mdata < 800))
                outband5[out_x, out_y] = np.sum(np.logical_and(mdata >= 800, mdata < 1600))
                outband6[out_x, out_y] = np.sum(np.logical_and(mdata >= 1600, mdata < 3000))
                outband7[out_x, out_y] = np.sum(np.logical_and(mdata >= 3000, mdata < 4500))
                outband8[out_x, out_y] = np.array([[np.sum(mdata >= 4500)]])

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

out = None
