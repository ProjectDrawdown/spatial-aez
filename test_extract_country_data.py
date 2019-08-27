import os.path
import pytest
import tempfile

import pandas as pd
import extract_country_data as ecd

def test_admin_lookup():
    assert ecd.admin_lookup('Cabo Verde') == 'Cape Verde'
    assert ecd.admin_lookup('Scarborough Reef') is None

def test_generate_csv():
    tmpdirobj = tempfile.TemporaryDirectory()
    shapefilename = 'ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp'
    worldmapname = 'Beck_KG_V1/Beck_KG_V1_present_0p5.tif'
    csvfilename = os.path.join(tmpdirobj.name, 'test.csv')
    assert not os.path.exists(csvfilename)
    ecd.main(shapefilename=shapefilename, worldmapname=worldmapname, tmpdir=tmpdirobj.name,
            csvfilename=csvfilename)
    assert os.path.exists(csvfilename)
    df = pd.read_csv(csvfilename).set_index('Country').sum(axis=1)
    assert 'United States of America' in df.index
    assert df['United States of America'] > 1
