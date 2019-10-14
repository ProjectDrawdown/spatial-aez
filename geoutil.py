#!/usr/bin/python
# vim: set fileencoding=utf-8 :

"""Geo-related utilities for Project Drawdown data pipelines."""

import math
import numpy as np
import osgeo.gdal

def km2_block(nrows, ncols, y_off, img):
    """Return (nrows,ncols) numpy array of pixel area in sq km."""
    x_mindeg, x_sizdeg, x_rot, y_mindeg, y_rotdeg, y_sizdeg = img.GetGeoTransform()
    yrad = math.radians(abs(y_sizdeg))
    km2 = np.empty((nrows, ncols))
    y = math.radians(y_mindeg + (y_off * y_sizdeg)) - (yrad / 2)
    for i in range(nrows):
        # https://en.wikipedia.org/wiki/Longitude#Length_of_a_degree_of_longitude
        xlen = abs(x_sizdeg) * (math.cos(y) * math.pi * 6378.137 /
                (180 * math.sqrt(1 - 0.00669437999014 * (math.sin(y) ** 2))))
        # https://en.wikipedia.org/wiki/Latitude#Length_of_a_degree_of_latitude
        ylen = abs(y_sizdeg) * (111.132954 - (0.559822 * math.cos(2 * y)) +
                (0.001175 * math.cos(4 * y)))
        km2[i, :] = xlen * ylen
        y -= yrad
    return km2


def is_sparse(band, x, y, ncols, nrows):
    """Return True if the given coordinates are a sparse hole in the image."""
    (flags, pct) = band.GetDataCoverageStatus(x, y, ncols, nrows)
    if flags == osgeo.gdal.GDAL_DATA_COVERAGE_STATUS_EMPTY and pct == 0.0:
        return True


def blklim(coord, blksiz, totsiz):
    """Return block dimensions, limited by the totsiz of the image."""
    if (coord + blksiz) < totsiz:
        return blksiz
    else:
        return totsiz - coord
