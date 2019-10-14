#!/usr/bin/python
# vim: set fileencoding=utf-8 :

"""Extract counts of each Köppen-Geiger/slope/land cover/soil health for each country,
   for use in Project Drawdown solution models."""
import argparse
import math
import os.path
import pdb
import signal
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


def populate_tmr(kg_blk):
    regime = {}
    regime['invalid'] = np.logical_or(kg_blk == 0, kg_blk > 30)
    regime['tropical-humid'] = np.logical_or.reduce((kg_blk == 1, kg_blk == 2, kg_blk == 3))
    regime['arid'] = np.logical_or(kg_blk == 4, kg_blk == 5)
    regime['tropical-semiarid'] = np.logical_or(kg_blk == 6, kg_blk == 7)
    regime['temperate/boreal-semiarid'] = np.logical_or.reduce((kg_blk == 8, kg_blk == 9,
            kg_blk == 10, kg_blk == 17, kg_blk == 18, kg_blk == 19, kg_blk == 20,
            kg_blk == 21, kg_blk == 22, kg_blk == 23, kg_blk == 24))
    regime['temperate/boreal-humid'] = np.logical_or.reduce((kg_blk == 11, kg_blk == 12,
            kg_blk == 13, kg_blk == 14, kg_blk == 15, kg_blk == 16, kg_blk == 25,
            kg_blk == 26, kg_blk == 27, kg_blk == 28))
    regime['arctic'] = np.logical_or(kg_blk == 29, kg_blk == 30)
    return regime


def populate_slope(sl_blk):
    slope = {}
    slope['minimal'] = sl_blk < 8.0
    slope['moderate'] = np.logical_and(sl_blk >= 8.0, sl_blk < 30.0)
    slope['steep'] = sl_blk >= 30.0
    return slope


def populate_land_use(lc_blk):
    land_use = {}
    land_use['forest'] = np.logical_or.reduce((lc_blk == 12, lc_blk == 50,
            lc_blk == 60, lc_blk == 61, lc_blk == 62,
            lc_blk == 70, lc_blk == 71, lc_blk == 72,
            lc_blk == 80, lc_blk == 81, lc_blk == 82,
            lc_blk == 90, lc_blk == 160, lc_blk == 170))
    land_use['cropland_rainfed'] = np.logical_or(lc_blk == 10, lc_blk == 30)
    land_use['cropland_irrigated'] = (lc_blk == 20)
    land_use['grassland'] = np.logical_or.reduce((lc_blk == 11, lc_blk == 40,
            lc_blk == 100, lc_blk == 110, lc_blk == 120, lc_blk == 121, lc_blk == 122,
            lc_blk == 130, lc_blk == 150, lc_blk == 151, lc_blk == 152, lc_blk == 153,
            lc_blk == 180))
    land_use['bare'] = np.logical_or.reduce((lc_blk == 140, lc_blk == 200,
            lc_blk == 201, lc_blk == 202))
    land_use['urban'] = (lc_blk == 190)
    land_use['water'] = (lc_blk == 210)
    land_use['ice'] = (lc_blk == 220)
    return land_use


def populate_soil_health(wk_blk):
    soil_health = {}
    soil_health['prime'] = (wk_blk == 1)
    soil_health['good'] = (wk_blk == 2)
    soil_health['marginal'] = np.logical_or(wk_blk == 3, wk_blk == 4)
    soil_health['bare'] = np.logical_or(wk_blk == 5, wk_blk == 6)
    soil_health['water'] = (wk_blk == 7)
    return soil_health


def populate_aez(df, admin, km2_blk, regime, tmr, slope, land_use, soil_health):
    df.loc[admin, f"{tmr}|AEZ1"] += (km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['forest'], soil_health['prime'], slope['minimal']))]).sum()
    df.loc[admin, f"{tmr}|AEZ2"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['forest'], soil_health['good'], slope['minimal']))].sum()
    df.loc[admin, f"{tmr}|AEZ3"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['forest'], soil_health['good'], slope['moderate']))].sum()
    df.loc[admin, f"{tmr}|AEZ3"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['forest'], soil_health['prime'], slope['moderate']))].sum()
    df.loc[admin, f"{tmr}|AEZ4"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['forest'], soil_health['good'], slope['steep']))].sum()
    df.loc[admin, f"{tmr}|AEZ4"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['forest'], soil_health['prime'], slope['steep']))].sum()
    df.loc[admin, f"{tmr}|AEZ5"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['forest'], soil_health['marginal'], slope['minimal']))].sum()
    df.loc[admin, f"{tmr}|AEZ6"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['forest'], soil_health['marginal'], slope['moderate']))].sum()
    df.loc[admin, f"{tmr}|AEZ7"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['forest'], soil_health['marginal'], slope['steep']))].sum()
    df.loc[admin, f"{tmr}|AEZ8"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['grassland'], soil_health['prime'], slope['minimal']))].sum()
    df.loc[admin, f"{tmr}|AEZ9"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['grassland'], soil_health['good'], slope['minimal']))].sum()
    df.loc[admin, f"{tmr}|AEZ10"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['grassland'], soil_health['good'], slope['moderate']))].sum()
    df.loc[admin, f"{tmr}|AEZ10"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['grassland'], soil_health['prime'], slope['moderate']))].sum()
    df.loc[admin, f"{tmr}|AEZ11"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['grassland'], soil_health['good'], slope['steep']))].sum()
    df.loc[admin, f"{tmr}|AEZ11"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['grassland'], soil_health['prime'], slope['steep']))].sum()
    df.loc[admin, f"{tmr}|AEZ12"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['grassland'], soil_health['marginal'], slope['minimal']))].sum()
    df.loc[admin, f"{tmr}|AEZ13"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['grassland'], soil_health['marginal'], slope['moderate']))].sum()
    df.loc[admin, f"{tmr}|AEZ14"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['grassland'], soil_health['marginal'], slope['steep']))].sum()
    df.loc[admin, f"{tmr}|AEZ15"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['cropland_irrigated'], soil_health['prime'], slope['minimal']))].sum()
    df.loc[admin, f"{tmr}|AEZ16"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['cropland_irrigated'], soil_health['good'], slope['minimal']))].sum()
    df.loc[admin, f"{tmr}|AEZ17"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['cropland_irrigated'], soil_health['good'], slope['moderate']))].sum()
    df.loc[admin, f"{tmr}|AEZ17"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['cropland_irrigated'], soil_health['prime'], slope['moderate']))].sum()
    df.loc[admin, f"{tmr}|AEZ18"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['cropland_irrigated'], soil_health['good'], slope['steep']))].sum()
    df.loc[admin, f"{tmr}|AEZ18"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['cropland_irrigated'], soil_health['prime'], slope['steep']))].sum()
    df.loc[admin, f"{tmr}|AEZ19"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['cropland_irrigated'], soil_health['marginal'], slope['minimal']))].sum()
    df.loc[admin, f"{tmr}|AEZ20"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['cropland_irrigated'], soil_health['marginal'], slope['moderate']))].sum()
    df.loc[admin, f"{tmr}|AEZ21"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['cropland_irrigated'], soil_health['marginal'], slope['steep']))].sum()
    df.loc[admin, f"{tmr}|AEZ22"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['cropland_rainfed'], soil_health['prime'], slope['minimal']))].sum()
    df.loc[admin, f"{tmr}|AEZ23"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['cropland_rainfed'], soil_health['good'], slope['minimal']))].sum()
    df.loc[admin, f"{tmr}|AEZ24"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['cropland_rainfed'], soil_health['good'], slope['moderate']))].sum()
    df.loc[admin, f"{tmr}|AEZ24"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['cropland_rainfed'], soil_health['prime'], slope['moderate']))].sum()
    df.loc[admin, f"{tmr}|AEZ25"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['cropland_rainfed'], soil_health['good'], slope['steep']))].sum()
    df.loc[admin, f"{tmr}|AEZ25"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['cropland_rainfed'], soil_health['prime'], slope['steep']))].sum()
    df.loc[admin, f"{tmr}|AEZ26"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['cropland_rainfed'], soil_health['marginal'], slope['minimal']))].sum()
    df.loc[admin, f"{tmr}|AEZ27"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['cropland_rainfed'], soil_health['marginal'], slope['moderate']))].sum()
    df.loc[admin, f"{tmr}|AEZ28"] += km2_blk[np.logical_and.reduce((regime[tmr],
        land_use['cropland_rainfed'], soil_health['marginal'], slope['steep']))].sum()
    df.loc[admin, f"{tmr}|AEZ29"] += km2_blk[np.logical_and(regime[tmr],
        np.logical_or.reduce((
            land_use['bare'], land_use['water'], land_use['ice'], land_use['urban'],
            soil_health['bare'], soil_health['water'])))].sum()


def process_aez():
    """Produce a CSV file of Thermal Moisture Regime + Agro-Ecological Zone per country."""
    tmr_names = ['tropical-humid', 'arid', 'tropical-semiarid', 'temperate/boreal-humid',
                 'temperate/boreal-semiarid', 'arctic', 'invalid']
    columns = []
    for tmr in tmr_names:
        columns.extend([f"{tmr}|AEZ{x}" for x in range(0, 30)])
    df = pd.DataFrame(columns=columns, dtype='float')
    df.index.name = 'Country'

    csvfilename = 'results/AEZ-by-country.csv'
    shapefilename = 'data/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp'
    kg_filename = 'data/Beck_KG_V1/Beck_KG_V1_present_0p0083.tif'
    lc_filename = 'data/ucl_elie/ESACCI-LC-L4-LCCS-Map-300m-P1Y-2015-v2.0.7.tif'
    sl_filename = 'data/geomorpho90m/classified_slope_merit_dem_1km_s0..0cm_2018_v1.0.tif'
    wk_filename = 'data/FAO/workability_FAO_sq7_1km.tif'
    shapefile = osgeo.ogr.Open(shapefilename)
    assert shapefile.GetLayerCount() == 1
    layer = shapefile.GetLayerByIndex(0)
    kg_img = osgeo.gdal.Open(kg_filename, osgeo.gdal.GA_ReadOnly)
    kg_band = kg_img.GetRasterBand(1)
    lc_img = osgeo.gdal.Open(lc_filename, osgeo.gdal.GA_ReadOnly)
    lc_band = lc_img.GetRasterBand(1)
    sl_img = osgeo.gdal.Open(sl_filename, osgeo.gdal.GA_ReadOnly)
    sl_band = sl_img.GetRasterBand(9)
    wk_img = osgeo.gdal.Open(wk_filename, osgeo.gdal.GA_ReadOnly)
    wk_band = wk_img.GetRasterBand(1)

    for idx, feature in enumerate(layer):
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

                k = kg_band.ReadAsArray(x, y, ncols, nrows)
                kg_blk = np.repeat(np.repeat(k, 3, axis=1), 3, axis=0)
                regime = populate_tmr(kg_blk)

                s = sl_band.ReadAsArray(x, y, ncols, nrows)
                sl_blk = np.repeat(np.repeat(s, 3, axis=1), 3, axis=0)
                slope = populate_slope(sl_blk)

                lc_blk = lc_band.ReadAsArray(3*x, 3*y, 3*ncols, 3*nrows)
                land_use = populate_land_use(lc_blk)

                w = wk_band.ReadAsArray(x, y, ncols, nrows)
                wk_blk = np.repeat(np.repeat(w, 3, axis=1), 3, axis=0)
                soil_health = populate_soil_health(wk_blk)

                for tmr in tmr_names:
                    populate_aez(df=df, admin=admin, km2_blk=km2_blk, regime=regime, tmr=tmr,
                            slope=slope, land_use=land_use, soil_health=soil_health)

    df.sort_index(axis='index').to_csv(csvfilename, float_format='%.2f')


if __name__ == '__main__':
    signal.signal(signal.SIGUSR1, start_pdb)
    os.environ['GDAL_CACHEMAX'] = '128'
    process_aez()
