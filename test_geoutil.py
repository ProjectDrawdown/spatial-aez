import numpy as np
import osgeo.gdal
import pytest

import geoutil

imgfilename = 'test_geoutil._tif'

def test_km2_block():
    img = osgeo.gdal.Open(imgfilename, osgeo.gdal.GA_ReadOnly)

    # at equator, 1 degree == 111.132954 meters. We're making a very rough approximation
    # which doesn't include the Earth's bulge around the equator.
    siz = 111.132954 * 0.008333333333333
    expected = np.array([[siz ** 2]])
    actual = geoutil.km2_block(nrows=1, ncols=1, y_off=((21600/2) - 1), img=img)
    assert actual == pytest.approx(expected, rel=1e-2)

def test_is_sparse():
    img = osgeo.gdal.Open(imgfilename, osgeo.gdal.GA_ReadOnly)
    band = img.GetRasterBand(1)
    assert geoutil.is_sparse(band=band, x=0, y=0, ncols=256, nrows=256) is True
    # approximate center of the US.
    assert geoutil.is_sparse(band=band, x=9970, y=6020, ncols=256, nrows=256) is not True


def test_blklim():
    assert geoutil.blklim(coord=0, blksiz=256, totsiz=1024) == 256
    assert geoutil.blklim(coord=768, blksiz=256, totsiz=1024) == 256
    assert geoutil.blklim(coord=900, blksiz=256, totsiz=1024) == 124
