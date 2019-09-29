import math
import os
import time

import numpy as np
import osgeo.gdal
import osgeo.gdal_array

def orig(filename):
    img = osgeo.gdal.Open(filename, osgeo.gdal.GA_ReadOnly)
    xmin, xsiz, xrot, ymin, yrot, ysiz = img.GetGeoTransform()
    img = None
    arr = osgeo.gdal_array.LoadFile(filename)
    yrad = math.radians(abs(ysiz))
    y = math.radians(ymin)
    yoff = 0
    for row in arr:
        y1 = y - (yrad / 2)
        # https://en.wikipedia.org/wiki/Longitude#Length_of_a_degree_of_longitude
        xlen = abs(xsiz) * (math.cos(y1) * math.pi * 6378.137 /
                (180 * math.sqrt(1 - 0.00669437999014 * (math.sin(y1) ** 2))))
        # https://en.wikipedia.org/wiki/Latitude#Length_of_a_degree_of_latitude
        ylen = abs(ysiz) * (111.132954 - (0.559822 * math.cos(2 * y1)) +
                (0.001175 * math.cos(4 * y1)))
        km2 = xlen * ylen
        u, c = np.unique(row, return_counts=True)
        y -= yrad
        yoff = yoff + 1
        if yoff > 100:
            return


def perf(filename):
    img = osgeo.gdal.Open(filename, osgeo.gdal.GA_ReadOnly)
    xmin, xsiz, xrot, ymin, yrot, ysiz = img.GetGeoTransform()
    band = img.GetRasterBand(1)
    yrad = math.radians(abs(ysiz))
    y = math.radians(ymin)
    print(f"{int(band.XSize)} {int(band.YSize)}")
    for yoff in range(0, int(band.YSize)):
        row = band.ReadAsArray(0, yoff, int(band.XSize), 1)
        y1 = y - (yrad / 2)
        # https://en.wikipedia.org/wiki/Longitude#Length_of_a_degree_of_longitude
        xlen = abs(xsiz) * (math.cos(y1) * math.pi * 6378.137 /
                (180 * math.sqrt(1 - 0.00669437999014 * (math.sin(y1) ** 2))))
        # https://en.wikipedia.org/wiki/Latitude#Length_of_a_degree_of_latitude
        ylen = abs(ysiz) * (111.132954 - (0.559822 * math.cos(2 * y1)) +
                (0.001175 * math.cos(4 * y1)))
        km2 = xlen * ylen
        u, c = np.unique(row[0], return_counts=True)
        _ = u.sum()
        _ = c.sum()
        y -= yrad


os.environ['GDAL_CACHEMAX'] = '0'

for filename in [#'data/ucl_elie/ESACCI-LC-L4-LCCS-Map-300m-P1Y-2015-v2.0.7.tif',
                 #'data/Beck_KG_V1/Beck_KG_V1_present_0p0083.tif',
                 #'data/Beck_KG_V1/Beck_KG_V1_future_0p0083.tif',
                 #'data/geomorpho90m/classified_slope_merit_dem_250m_s0..0cm_2018_v1.0.tif',
                 #'data/FAO/workability_FAO_sq7_10km.tif',
                 'testdata/slope_MNG_cutfile.tif']:
    print(filename)

    start = time.monotonic()
    perf(filename)
    end = time.monotonic()
    print(f"perf: {(end - start):02f}")

    start = time.monotonic()
    orig(filename)
    end = time.monotonic()
    print(f"orig: {(end - start):02f}")

    start = time.monotonic()
    perf(filename)
    end = time.monotonic()
    print(f"perf: {(end - start):02f}")


