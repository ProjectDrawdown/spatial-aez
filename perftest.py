import math
import os
import time

import numpy as np
import osgeo.gdal
import osgeo.gdal_array

def perf(filename):
    img = osgeo.gdal.Open(filename, osgeo.gdal.GA_ReadOnly)
    xmin, xsiz, xrot, ymin, yrot, ysiz = img.GetGeoTransform()
    band = img.GetRasterBand(1)
    yrad = math.radians(abs(ysiz))
    y = math.radians(ymin)
    print(f"{band.XSize} {band.YSize}")
    for yoff in range(0, int(band.YSize) + 1):
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
        y -= yrad
        if yoff > 100:
            print(f"100! row {row} len {len(row[0])} u {u} c {c}")
            return


os.environ['GDAL_CACHEMAX'] = '128'
start = time.monotonic()
perf('data/ucl_elie/ESACCI-LC-L4-LCCS-Map-300m-P1Y-2015-v2.0.7.tif')
end = time.monotonic()
print(f"time: {(end - start):02f}")
