import os.path
import pytest
import tempfile

import osgeo.gdal
import pandas as pd
import extract_country_data as ecd

def test_kg():
    shapefilename = 'data/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp'
    mapfilename = 'data/Beck_KG_V1/Beck_KG_V1_present_0p5.tif'
    img = osgeo.gdal.Open(mapfilename, osgeo.gdal.GA_ReadOnly)
    ctable = img.GetRasterBand(1).GetColorTable()
    lookupobj = ecd.KGlookup(ctable)
    csvfile = tempfile.NamedTemporaryFile()
    assert os.path.getsize(csvfile.name) == 0
    ecd.process_map(shapefilename=shapefilename, mapfilename=mapfilename, lookupobj=lookupobj,
                    csvfilename=csvfile.name)
    assert os.path.getsize(csvfile.name) != 0
    df = pd.read_csv(csvfile.name).set_index('Country').sum(axis=1)
    assert 'United States of America' in df.index
    assert df['United States of America'] > 1

def test_lc():
    shapefilename = 'data/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp'
    mapfilename = 'data/ucl_elie/test_small.tif'
    lookupobj = ecd.LClookup()
    csvfile = tempfile.NamedTemporaryFile()
    assert os.path.getsize(csvfile.name) == 0
    ecd.process_map(shapefilename=shapefilename, mapfilename=mapfilename, lookupobj=lookupobj,
                    csvfilename=csvfile.name)
    assert os.path.getsize(csvfile.name) != 0
    df = pd.read_csv(csvfile.name).set_index('Country').sum(axis=1)
    assert 'United States of America' in df.index
    assert df['United States of America'] > 1

def test_sl():
    shapefilename = 'data/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp'
    mapfilename = 'data/geomorpho90m/test_small.tif'
    lookupobj = ecd.SlopeLookup()
    csvfile = tempfile.NamedTemporaryFile()
    assert os.path.getsize(csvfile.name) == 0
    ecd.process_map(shapefilename=shapefilename, mapfilename=mapfilename, lookupobj=lookupobj,
                    csvfilename=csvfile.name)
    assert os.path.getsize(csvfile.name) != 0
    df = pd.read_csv(csvfile.name).set_index('Country').sum(axis=1)
    assert 'United States of America' in df.index
    assert df['United States of America'] > 1
