#!/usr/bin/python
# vim: set fileencoding=utf-8 :

import argparse
import math
import os.path
import pdb
import signal
import subprocess
import sys
import tempfile

import osgeo.gdal
import osgeo.gdal_array
import osgeo.ogr
import numpy as np
import pandas as pd

import admin_names
import geoutil


pd.set_option("display.max_rows", 500)
pd.set_option("display.max_columns", 40)
pd.options.display.float_format = '{:.2f}'.format
osgeo.gdal.PushErrorHandler("CPLQuietErrorHandler")
np.set_printoptions(threshold=sys.maxsize)


def start_pdb(sig, frame):
    """Start PDB on a signal."""
    pdb.Pdb().set_trace(frame)


def produce_CSV():
    """Produce a CSV file of degraded land for {forest, cropland, grassland}."""
    columns = ['forest:degraded', 'forest:nondegraded',
            'cropland:degraded', 'cropland:nondegraded',
            'grassland:degraded', 'grassland:nondegraded',
            'bare:degraded', 'bare:nondegraded',
            'urban:degraded', 'urban:nondegraded',
            'water:degraded', 'water:nondegraded',
            'ice:degraded', 'ice:nondegraded']
    df = pd.DataFrame(columns=columns, dtype='float')
    df.index.name = 'Country'

    shapefilename = 'data/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp'
    shapefile = osgeo.ogr.Open(shapefilename)
    assert shapefile.GetLayerCount() == 1
    features = shapefile.GetLayerByIndex(0)
    lc_filename = 'data/ucl_elie/ESACCI-LC-L4-LCCS-Map-300m-P1Y-2015-v2.0.7.tif'
    lc_img = osgeo.gdal.Open(lc_filename, osgeo.gdal.GA_ReadOnly)
    lc_band = lc_img.GetRasterBand(1)

    lpd_filename = 'data/lpd_int2/lpd_int2.tif'
    lpd_img = osgeo.gdal.Open(lpd_filename, osgeo.gdal.GA_ReadOnly)
    lpd_band = lpd_img.GetRasterBand(1)

    for idx, feature in enumerate(features):
        admin = admin_names.lookup(feature.GetField("ADMIN"))
        if admin is None:
            continue
        a3 = feature.GetField("SOV_A3")
        if admin not in df.index:
            df.loc[admin] = [0] * len(df.columns)

        print(f"Processing {admin:<41} #{a3}_{idx}")
        maskfilename = f"masks/{a3}_{idx}_1km_mask._tif"
        maskimg = osgeo.gdal.Open(maskfilename, osgeo.gdal.GA_ReadOnly)
        mask_band = maskimg.GetRasterBand(1)
        x_siz = mask_band.XSize
        y_siz = mask_band.YSize
        x_blksiz, y_blksiz = mask_band.GetBlockSize()
        for y in range(0, y_siz, y_blksiz):
            nrows = geoutil.blklim(coord=y, blksiz=y_blksiz, totsiz=y_siz)
            for x in range(0, x_siz, x_blksiz):
                ncols = geoutil.blklim(coord=x, blksiz=x_blksiz, totsiz=x_siz)
                if geoutil.is_sparse(band=mask_band, x=x, y=y, ncols=ncols, nrows=nrows):
                    # sparse hole in image, no data to process
                    continue

                mask_blk = mask_band.ReadAsArray(x, y, ncols, nrows)
                k = geoutil.km2_block(nrows=nrows, ncols=ncols, y_off=y, img=maskimg)
                k[np.logical_not(mask_blk)] = 0.0
                km2_blk = (np.repeat(np.repeat(k, 3, axis=1), 3, axis=0)) / 9.0

                lc_blk = lc_band.ReadAsArray(3*x, 3*y, 3*ncols, 3*nrows)
                forest = np.logical_or.reduce((lc_blk == 12, lc_blk == 50,
                        lc_blk == 60, lc_blk == 61, lc_blk == 62,
                        lc_blk == 70, lc_blk == 71, lc_blk == 72,
                        lc_blk == 80, lc_blk == 81, lc_blk == 82,
                        lc_blk == 90, lc_blk == 160, lc_blk == 170))
                cropland = np.logical_or.reduce((lc_blk == 10, lc_blk == 30,
                        lc_blk == 20))
                grassland = np.logical_or.reduce((lc_blk == 11, lc_blk == 40,
                        lc_blk == 100, lc_blk == 110, lc_blk == 120, lc_blk == 121, lc_blk == 122,
                        lc_blk == 130, lc_blk == 150, lc_blk == 151, lc_blk == 152, lc_blk == 153,
                        lc_blk == 180))
                bare = np.logical_or.reduce((lc_blk == 140, lc_blk == 200, lc_blk == 201, lc_blk == 202))
                urban = (lc_blk == 190)
                water = (lc_blk == 210)
                ice = (lc_blk == 220)

                k = lpd_band.ReadAsArray(x, y, ncols, nrows)
                lpd_blk = np.repeat(np.repeat(k, 3, axis=1), 3, axis=0)
                degraded = (lpd_blk != 0.0)
                nondegraded = (lpd_blk == 0.0)

                df.loc[admin, 'forest:degraded'] += (np.logical_and(forest, degraded) * km2_blk).sum()
                df.loc[admin, 'forest:nondegraded'] += (np.logical_and(forest, nondegraded) * km2_blk).sum()
                df.loc[admin, 'cropland:degraded'] += (np.logical_and(cropland, degraded) * km2_blk).sum()
                df.loc[admin, 'cropland:nondegraded'] += (np.logical_and(cropland, nondegraded) * km2_blk).sum()
                df.loc[admin, 'grassland:degraded'] += (np.logical_and(grassland, degraded) * km2_blk).sum()
                df.loc[admin, 'grassland:nondegraded'] += (np.logical_and(grassland, nondegraded) * km2_blk).sum()
                df.loc[admin, 'bare:degraded'] += (np.logical_and(bare, degraded) * km2_blk).sum()
                df.loc[admin, 'bare:nondegraded'] += (np.logical_and(bare, nondegraded) * km2_blk).sum()
                df.loc[admin, 'urban:degraded'] += (np.logical_and(urban, degraded) * km2_blk).sum()
                df.loc[admin, 'urban:nondegraded'] += (np.logical_and(urban, nondegraded) * km2_blk).sum()
                df.loc[admin, 'water:degraded'] += (np.logical_and(water, degraded) * km2_blk).sum()
                df.loc[admin, 'water:nondegraded'] += (np.logical_and(water, nondegraded) * km2_blk).sum()
                df.loc[admin, 'ice:degraded'] += (np.logical_and(ice, degraded) * km2_blk).sum()
                df.loc[admin, 'ice:nondegraded'] += (np.logical_and(ice, nondegraded) * km2_blk).sum()

    csvfilename = 'results/degraded-cover-by-country.csv'
    df.sort_index(axis='index').to_csv(csvfilename, float_format='%.2f')

    regions = ['OECD90', 'Eastern Europe', 'Asia (Sans Japan)', 'Middle East and Africa',
            'Latin America', 'China', 'India', 'EU', 'USA']
    df_region = pd.DataFrame(0, index=regions, columns=df.columns.copy())
    df_region.index.name = 'Region'
    for country, row in df.iterrows():
        region = admin_names.region_mapping[country]
        if region is not None:
            df_region.loc[region, :] += row
    csvfilename = f"results/degraded-cover-by-region.csv"
    df_region.to_csv(csvfilename, float_format='%.2f')


if __name__ == '__main__':
    signal.signal(signal.SIGUSR1, start_pdb)
    os.environ['GDAL_CACHEMAX'] = '128'
    produce_CSV()
