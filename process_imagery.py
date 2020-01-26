#!/usr/bin/python
# vim: set fileencoding=utf-8 :

"""Extract counts of each Köppen-Geiger/slope/land cover/soil health for each country,
   for use in Project Drawdown solution models."""
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


# color table entries
C_TMR_TRHU =   0  # tropical-humid
C_TMR_ARID =  30  # arid
C_TMR_TRSA =  60  # tropical-semiarid
C_TMR_THU  =  90  # temperate-humid
C_TMR_TSA  = 120  # temperate-semiarid
C_TMR_BHU  = 150  # boreal-humid
C_TMR_BSA  = 180  # boreal-semiarid
C_TMR_ARTC = 210  # arctic
C_TMR_BLNK = 255

C_SLP_MIN  =   0  # minimal slope
C_SLP_MOD  =   1  # moderate slope
C_SLP_STP  =   2  # steep slope
C_SLP_BLNK =   3

C_LUS_FRST =   0  # forest
C_LUS_CRRF =   1  # cropland, rainfed
C_LUS_CRIR =   2  # cropland, irrigated
C_LUS_GRSS =   3  # grassland
C_LUS_BARE =   4  # bare land
C_LUS_URBN =   5  # urban
C_LUS_WATR =   6  # water
C_LUS_ICE  =   7  # ice
C_LUS_BLNK =   8

C_SLH_GOOD =   0  # good
C_SLH_MRGN =   1  # marginal
C_SLH_POOR =   2  # poor
C_SLH_BARE =   4  # barren
C_SLH_WATR =   5  # water
C_SLH_BLNK =   6

tmr_state = {
        'tropical-humid': C_TMR_TRHU,
        'arid': C_TMR_ARID,
        'tropical-semiarid': C_TMR_TRSA,
        'temperate-humid': C_TMR_THU,
        'temperate-semiarid': C_TMR_TSA,
        'boreal-humid': C_TMR_BHU,
        'boreal-semiarid': C_TMR_BSA,
        'arctic': C_TMR_ARTC,
        }


def start_pdb(sig, frame):
    """Start PDB on a signal."""
    pdb.Pdb().set_trace(frame)


def populate_tmr(kg_blk):
    regime = {}
    regime['invalid'] = np.logical_or(kg_blk == 0, kg_blk > 30)
    regime['tropical-humid'] = np.logical_or.reduce((kg_blk == 1, kg_blk == 2, kg_blk == 3))
    regime['arid'] = np.logical_or(kg_blk == 4, kg_blk == 5)
    regime['tropical-semiarid'] = np.logical_or(kg_blk == 6, kg_blk == 7)
    regime['temperate-semiarid'] = np.logical_or.reduce((kg_blk == 8, kg_blk == 9, kg_blk == 10))
    regime['temperate-humid'] = np.logical_or.reduce((kg_blk == 11, kg_blk == 12,
            kg_blk == 13, kg_blk == 14, kg_blk == 15, kg_blk == 16))
    regime['boreal-semiarid'] = np.logical_or.reduce((kg_blk == 17, kg_blk == 18,
            kg_blk == 19, kg_blk == 20, kg_blk == 21, kg_blk == 22, kg_blk == 23, kg_blk == 24))
    regime['boreal-humid'] = np.logical_or.reduce((kg_blk == 25,
            kg_blk == 26, kg_blk == 27, kg_blk == 28))
    regime['arctic'] = np.logical_or(kg_blk == 29, kg_blk == 30)
    return regime


def populate_slope(sl_blk):
    slope = {}
    slope['minimal'] = (sl_blk[1] + sl_blk[2] + sl_blk[3] + sl_blk[4]) / 100.0
    slope['moderate'] = (sl_blk[5] + sl_blk[6]) / 100.0
    slope['steep'] = (sl_blk[7] + sl_blk[8]) / 100.0
    return slope


def populate_land_use(lc_blk):
    land_use = {}
    land_use['forest'] = np.logical_or.reduce((lc_blk == 12, lc_blk == 50,
            lc_blk == 60, lc_blk == 61, lc_blk == 62, lc_blk == 70, lc_blk == 71, lc_blk == 72,
            lc_blk == 80, lc_blk == 81, lc_blk == 82, lc_blk == 90, lc_blk == 100,
            lc_blk == 160, lc_blk == 170))
    land_use['cropland_rainfed'] = np.logical_or(lc_blk == 10, lc_blk == 30)
    land_use['cropland_irrigated'] = (lc_blk == 20)
    land_use['grassland'] = np.logical_or.reduce((lc_blk == 11, lc_blk == 40, lc_blk == 110,
            lc_blk == 120, lc_blk == 121, lc_blk == 122,
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
    soil_health['marginal'] = np.logical_or.reduce((wk_blk == 3, wk_blk == 4, wk_blk == 6))
    soil_health['barren'] = (wk_blk == 5)
    soil_health['water'] = (wk_blk == 7)
    return soil_health


def yield_AEZs(regime, tmr, slope, land_use, soil_health):
    # AEZ1: Forest, prime, minimal
    yield regime[tmr] * land_use['forest'] * soil_health['prime'] * slope['minimal']
    # AEZ2: Forest, good, minimal
    yield regime[tmr] * land_use['forest'] * soil_health['good'] * slope['minimal']
    # AEZ3: Forest, good, moderate
    yield regime[tmr] * land_use['forest'] * (soil_health['good'] + soil_health['prime']) * slope['moderate']
    # AEZ4: Forest, good, steep
    yield regime[tmr] * land_use['forest'] * (soil_health['good'] + soil_health['prime']) * slope['steep']
    # AEZ5: Forest, marginal, minimal
    yield regime[tmr] * land_use['forest'] * soil_health['marginal'] * slope['minimal']
    # AEZ6: Forest, marginal, moderate
    yield regime[tmr] * land_use['forest'] * soil_health['marginal'] * slope['moderate']
    # AEZ7: Forest, marginal, steep
    yield regime[tmr] * land_use['forest'] * soil_health['marginal'] * slope['steep']
    # AEZ8: Grassland, prime, minimal
    yield regime[tmr] * land_use['grassland'] * soil_health['prime'] * slope['minimal']
    # AEZ9: Grassland, good, minimal
    yield regime[tmr] * land_use['grassland'] * soil_health['good'] * slope['minimal']
    # AEZ10: Grassland, good, moderate
    yield regime[tmr] * land_use['grassland'] * (soil_health['good'] + soil_health['prime']) * slope['moderate']
    # AEZ11: Grassland, good, steep
    yield regime[tmr] * land_use['grassland'] * (soil_health['good'] + soil_health['prime']) * slope['steep']
    # AEZ12: Grassland, marginal, minimal
    yield regime[tmr] * land_use['grassland'] * soil_health['marginal'] * slope['minimal']
    # AEZ13: Grassland, marginal, moderate
    yield regime[tmr] * land_use['grassland'] * soil_health['marginal'] * slope['moderate']
    # AEZ14: Grassland, marginal, steep
    yield regime[tmr] * land_use['grassland'] * soil_health['marginal'] * slope['steep']
    # AEZ15: Irrigated Cropland, prime, minimal
    yield regime[tmr] * land_use['cropland_irrigated'] * soil_health['prime'] * slope['minimal']
    # AEZ16: Irrigated Cropland, good, minimal
    yield regime[tmr] * land_use['cropland_irrigated'] * soil_health['good'] * slope['minimal']
    # AEZ17: Irrigated Cropland, good, moderate
    yield regime[tmr] * land_use['cropland_irrigated'] * (soil_health['good'] + soil_health['prime']) * slope['moderate']
    # AEZ18: Irrigated Cropland, good, steep
    yield regime[tmr] * land_use['cropland_irrigated'] * (soil_health['good'] + soil_health['prime']) * slope['steep']
    # AEZ19: Irrigated Cropland, marginal, minimal
    yield regime[tmr] * land_use['cropland_irrigated'] * soil_health['marginal'] * slope['minimal']
    # AEZ20: Irrigated Cropland, marginal, moderate
    yield regime[tmr] * land_use['cropland_irrigated'] * soil_health['marginal'] * slope['moderate']
    # AEZ21: Irrigated Cropland, marginal, steep
    yield regime[tmr] * land_use['cropland_irrigated'] * soil_health['marginal'] * slope['steep']
    # AEZ22: Rainfed Cropland, prime, minimal
    yield regime[tmr] * land_use['cropland_rainfed'] * soil_health['prime'] * slope['minimal']
    # AEZ23: Rainfed Cropland, good, minimal
    yield regime[tmr] * land_use['cropland_rainfed'] * soil_health['good'] * slope['minimal']
    # AEZ24: Rainfed Cropland, good, moderate
    yield regime[tmr] * land_use['cropland_rainfed'] * (soil_health['good'] + soil_health['prime']) * slope['moderate']
    # AEZ25: Rainfed Cropland, good, steep
    yield regime[tmr] * land_use['cropland_rainfed'] * (soil_health['good'] + soil_health['prime']) * slope['steep']
    # AEZ26: Rainfed Cropland, marginal, minimal
    yield regime[tmr] * land_use['cropland_rainfed'] * soil_health['marginal'] * slope['minimal']
    # AEZ27: Rainfed Cropland, marginal, moderate
    yield regime[tmr] * land_use['cropland_rainfed'] * soil_health['marginal'] * slope['moderate']
    # AEZ28: Rainfed Cropland, marginal, steep
    yield regime[tmr] * land_use['cropland_rainfed'] * soil_health['marginal'] * slope['steep']
    # AEZ29: All Barren Land
    bare = land_use['bare'] + land_use['ice'] + land_use['urban']
    barren = soil_health['barren']
    barren[bare] = 0.0  # avoid double counting
    yield regime[tmr] * (bare + barren)


def produce_CSV():
    """Produce a CSV file of Thermal Moisture Regime + Agro-Ecological Zone per country."""
    columns = []
    for tmr in tmr_state.keys():
        columns.extend([f"{tmr}|AEZ{x}" for x in range(1, 30)])
    df = pd.DataFrame(columns=columns, dtype='float')
    df.index.name = 'Country'

    countrycsvfilename = 'results/AEZ-by-country.csv'
    shapefilename = 'data/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp'
    kg_filename = 'data/Beck_KG_V1/Beck_KG_V1_present_0p0083.tif'
    lc_filename = 'data/copernicus/C3S-LC-L4-LCCS-Map-300m-P1Y-2018-v2.1.1.tif'
    sl_filename = 'data/ConsolidatedSlope.tif'
    wk_filename = 'data/FAO/workability_FAO_sq7_1km.tif'
    shapefile = osgeo.ogr.Open(shapefilename)
    assert shapefile.GetLayerCount() == 1
    features = shapefile.GetLayerByIndex(0)
    kg_img = osgeo.gdal.Open(kg_filename, osgeo.gdal.GA_ReadOnly)
    kg_band = kg_img.GetRasterBand(1)
    lc_img = osgeo.gdal.Open(lc_filename, osgeo.gdal.GA_ReadOnly)
    lc_band = lc_img.GetRasterBand(1)
    sl_img = osgeo.gdal.Open(sl_filename, osgeo.gdal.GA_ReadOnly)
    sl_band = {}
    for idx in range(1, 9):
        sl_band[idx] = sl_img.GetRasterBand(idx)
    wk_img = osgeo.gdal.Open(wk_filename, osgeo.gdal.GA_ReadOnly)
    wk_band = wk_img.GetRasterBand(1)

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

                k = kg_band.ReadAsArray(x, y, ncols, nrows)
                kg_blk = np.repeat(np.repeat(k, 3, axis=1), 3, axis=0)
                regime = populate_tmr(kg_blk)

                sl_blk = {}
                for idx in range(1, 9):
                    s = sl_band[idx].ReadAsArray(x, y, ncols, nrows)
                    sl_blk[idx] = np.repeat(np.repeat(s, 3, axis=1), 3, axis=0)
                slope = populate_slope(sl_blk)

                lc_blk = lc_band.ReadAsArray(3*x, 3*y, 3*ncols, 3*nrows)
                land_use = populate_land_use(lc_blk)

                w = wk_band.ReadAsArray(x, y, ncols, nrows)
                wk_blk = np.repeat(np.repeat(w, 3, axis=1), 3, axis=0)
                soil_health = populate_soil_health(wk_blk)

                for tmr in tmr_state.keys():
                    n = 1
                    for aez in yield_AEZs(regime=regime, tmr=tmr, slope=slope, land_use=land_use,
                            soil_health=soil_health):
                        df.loc[admin, f"{tmr}|AEZ{n}"] += (aez * km2_blk).sum()
                        n += 1

    df.sort_index(axis='index').to_csv(countrycsvfilename, float_format='%.2f')

    regions = ['OECD90', 'Eastern Europe', 'Asia (Sans Japan)', 'Middle East and Africa',
            'Latin America', 'China', 'India', 'EU', 'USA']
    df_region = pd.DataFrame(0, index=regions, columns=df.columns.copy())
    df_region.index.name = 'Region'
    for country, row in df.iterrows():
        region = admin_names.region_mapping[country]
        if region is not None:
            df_region.loc[region, :] += row

    for tmr in ['Tropical-Humid', 'Arid', 'Tropical-Semiarid', 'Temperate-Humid',
            'Temperate-Semiarid', 'Boreal-Humid', 'Boreal-Semiarid', 'Arctic']:
        tmrfilename = tmr.translate(str.maketrans('/', '-'))
        filename = f"results/AEZ-{tmrfilename}-by-region.csv"
        df_region.filter(regex=f'^{tmr.lower()}',axis=1).to_csv(filename, float_format='%.2f')



def create_AEZ_GeoTIFF(ref_img, filename):
    drv = osgeo.gdal.GetDriverByName(ref_img.GetDriver().ShortName)
    # LZMA:    159492702 bytes
    # DEFLATE: 158298535 bytes
    # ZSTD:    151202552 bytes (but not compatible with most non-GDAL 2.3+ TIFF apps)
    out = drv.Create(filename, xsize=ref_img.RasterXSize, ysize=ref_img.RasterYSize, bands=1,
            eType=osgeo.gdal.GDT_Byte, options = ['COMPRESS=DEFLATE', 'TILED=YES', 'NUM_THREADS=2'])
    out.SetProjection(ref_img.GetProjectionRef())
    out.SetGeoTransform(ref_img.GetGeoTransform())

    colors = osgeo.gdal.ColorTable()
    colors.SetColorEntry(C_TMR_BLNK, (0,0,0))

    colors.CreateColorRamp(C_TMR_TRHU, (0,192,0),   C_TMR_TRHU+29, (0,255,0))
    colors.CreateColorRamp(C_TMR_ARID, (128,128,0), C_TMR_ARID+29, (255,255,0))
    colors.CreateColorRamp(C_TMR_TRSA, (0,0,128),   C_TMR_TRSA+29, (0,0,255))
    colors.CreateColorRamp(C_TMR_THU,  (128,0,0),   C_TMR_THU+29,  (255,0,0))
    colors.CreateColorRamp(C_TMR_TSA,  (128,0,128), C_TMR_TSA+29,  (255,0,255))
    colors.CreateColorRamp(C_TMR_BHU,  (0,64,0),   C_TMR_BHU+29,  (0,128,0))
    colors.CreateColorRamp(C_TMR_BSA,  (0,128,128), C_TMR_BSA+29,  (0,255,255))
    colors.CreateColorRamp(C_TMR_ARTC, (64,64,64),  C_TMR_ARTC+29, (192,192,192))

    band = out.GetRasterBand(1)
    band.SetRasterColorTable(colors)
    band.SetRasterColorInterpretation(osgeo.gdal.GCI_PaletteIndex)

    return out

def create_slope_GeoTIFF(ref_img, filename):
    drv = osgeo.gdal.GetDriverByName(ref_img.GetDriver().ShortName)
    out = drv.Create(filename, xsize=ref_img.RasterXSize, ysize=ref_img.RasterYSize, bands=1,
            eType=osgeo.gdal.GDT_Byte,
            options = ['COMPRESS=DEFLATE', 'TILED=YES', 'NUM_THREADS=2', 'NBITS=2'])
    out.SetProjection(ref_img.GetProjectionRef())
    out.SetGeoTransform(ref_img.GetGeoTransform())

    colors = osgeo.gdal.ColorTable()
    colors.SetColorEntry(C_SLP_BLNK, (0,0,0))
    colors.SetColorEntry(C_SLP_MIN,  (32, 64, 32))   # minimal slope == light blue
    colors.SetColorEntry(C_SLP_MOD,  (32, 64, 96))   # moderate slope == medium blue
    colors.SetColorEntry(C_SLP_STP,  (32, 64, 240))  # steep slope == deep blue

    band = out.GetRasterBand(1)
    band.SetRasterColorTable(colors)
    band.SetRasterColorInterpretation(osgeo.gdal.GCI_PaletteIndex)

    return out


def create_land_use_GeoTIFF(ref_img, filename):
    drv = osgeo.gdal.GetDriverByName(ref_img.GetDriver().ShortName)
    out = drv.Create(filename, xsize=ref_img.RasterXSize, ysize=ref_img.RasterYSize, bands=1,
            eType=osgeo.gdal.GDT_Byte,
            options = ['COMPRESS=DEFLATE', 'TILED=YES', 'NUM_THREADS=2', 'NBITS=4'])
    out.SetProjection(ref_img.GetProjectionRef())
    out.SetGeoTransform(ref_img.GetGeoTransform())

    colors = osgeo.gdal.ColorTable()
    colors.SetColorEntry(C_LUS_BLNK, (0,0,0))
    colors.SetColorEntry(C_LUS_FRST, (49,113,35))   # forest == deep green
    colors.SetColorEntry(C_LUS_CRRF, (245,237,7))   # cropland_rainfed == yellow
    colors.SetColorEntry(C_LUS_CRIR, (227,175,18))  # cropland_irrigated == orange
    colors.SetColorEntry(C_LUS_GRSS, (99,222,123))  # grassland == light green
    colors.SetColorEntry(C_LUS_BARE, (80,80,80))    # bare == dark grey
    colors.SetColorEntry(C_LUS_URBN, (198,198,218)) # urban == light steel grey
    colors.SetColorEntry(C_LUS_WATR, (128,128,240)) # water == blue
    colors.SetColorEntry(C_LUS_ICE,  (240,240,248)) # ice == off-white

    band = out.GetRasterBand(1)
    band.SetRasterColorTable(colors)
    band.SetRasterColorInterpretation(osgeo.gdal.GCI_PaletteIndex)

    return out


def create_soil_health_GeoTIFF(ref_img, filename):
    drv = osgeo.gdal.GetDriverByName(ref_img.GetDriver().ShortName)
    out = drv.Create(filename, xsize=ref_img.RasterXSize, ysize=ref_img.RasterYSize, bands=1,
            eType=osgeo.gdal.GDT_Byte,
            options = ['COMPRESS=DEFLATE', 'TILED=YES', 'NUM_THREADS=2', 'NBITS=3'])
    out.SetProjection(ref_img.GetProjectionRef())
    out.SetGeoTransform(ref_img.GetGeoTransform())

    colors = osgeo.gdal.ColorTable()
    colors.SetColorEntry(C_SLH_BLNK, (0,0,0))
    colors.SetColorEntry(C_SLH_GOOD, (49,113,35))   # good == dark brown
    colors.SetColorEntry(C_SLH_MRGN, (212,145,0))   # marginal == light brown
    colors.SetColorEntry(C_SLH_POOR, (173,13,2))    # poor == reddish brown
    colors.SetColorEntry(C_SLH_BARE, (80,80,80))    # barren == dark grey
    colors.SetColorEntry(C_SLH_WATR, (128,128,240)) # water == blue

    band = out.GetRasterBand(1)
    band.SetRasterColorTable(colors)
    band.SetRasterColorInterpretation(osgeo.gdal.GCI_PaletteIndex)

    return out


def produce_GeoTIFF():
    """Produce a GeoTIFF file of Thermal Moisture Regime + Agro-Ecological Zone."""
    kg_filename = 'data/Beck_KG_V1/Beck_KG_V1_present_0p0083.tif'
    lc_filename = 'data/copernicus/C3S-LC-L4-LCCS-Map-300m-P1Y-2018-v2.1.1.tif'
    sl_filename = 'data/ConsolidatedSlope.tif'
    wk_filename = 'data/FAO/workability_FAO_sq7_1km.tif'
    kg_img = osgeo.gdal.Open(kg_filename, osgeo.gdal.GA_ReadOnly)
    kg_band = kg_img.GetRasterBand(1)
    lc_img = osgeo.gdal.Open(lc_filename, osgeo.gdal.GA_ReadOnly)
    lc_band = lc_img.GetRasterBand(1)
    sl_img = osgeo.gdal.Open(sl_filename, osgeo.gdal.GA_ReadOnly)
    sl_band = {}
    for idx in range(1, 9):
        sl_band[idx] = sl_img.GetRasterBand(idx)
    wk_img = osgeo.gdal.Open(wk_filename, osgeo.gdal.GA_ReadOnly)
    wk_band = wk_img.GetRasterBand(1)

    aez_f = create_AEZ_GeoTIFF(ref_img=lc_img, filename='results/AEZ.tif')
    slope_f = create_slope_GeoTIFF(ref_img=lc_img, filename='results/Slope.tif')
    land_use_f = create_land_use_GeoTIFF(ref_img=lc_img, filename='results/LandUse.tif')
    soil_health_f = create_soil_health_GeoTIFF(ref_img=lc_img, filename='results/SoilHealth.tif')

    x_siz = lc_band.XSize
    y_siz = lc_band.YSize
    x_blksiz, y_blksiz = (768, 768)

    for y in range(0, y_siz, y_blksiz):
        print('.', end='', flush=True)
        nrows = geoutil.blklim(coord=y, blksiz=y_blksiz, totsiz=y_siz)
        for x in range(0, x_siz, x_blksiz):
            ncols = geoutil.blklim(coord=x, blksiz=x_blksiz, totsiz=x_siz)

            x3 = int(x/3)
            y3 = int(y/3)
            ncols3 = int(ncols/3)
            nrows3 = int(nrows/3)

            k = kg_band.ReadAsArray(x3, y3, ncols3, nrows3)
            kg_blk = np.repeat(np.repeat(k, 3, axis=1), 3, axis=0)
            regime = populate_tmr(kg_blk)

            sl_blk = {}
            for idx in range(1, 9):
                s = sl_band[idx].ReadAsArray(x3, y3, ncols3, nrows3)
                sl_blk[idx] = np.repeat(np.repeat(s, 3, axis=1), 3, axis=0)

            slope = populate_slope(sl_blk)
            plurality = {}
            plurality['steep'] = ((slope['steep'] >= slope['moderate']) &
                    (slope['steep'] >= slope['minimal']))
            plurality['moderate'] = ((slope['moderate'] > slope['steep']) &
                    (slope['moderate'] >= slope['minimal']))
            plurality['minimal'] = ((slope['minimal'] > slope['steep']) &
                    (slope['minimal'] >= slope['moderate']))
            slope = plurality

            lc_blk = lc_band.ReadAsArray(x, y, ncols, nrows)
            land_use = populate_land_use(lc_blk)

            k = wk_band.ReadAsArray(x3, y3, ncols3, nrows3)
            wk_blk = np.repeat(np.repeat(k, 3, axis=1), 3, axis=0)
            soil_health = populate_soil_health(wk_blk)

            outarray = np.full((nrows, ncols), C_TMR_BLNK)
            for tmr, color in tmr_state.items():
                for aez in yield_AEZs(regime=regime, tmr=tmr, slope=slope, land_use=land_use,
                        soil_health=soil_health):
                    outarray[aez.astype(bool)] = color
                    color += 1
            aez_f.GetRasterBand(1).WriteArray(outarray, xoff=x, yoff=y)

            outarray = np.full((nrows, ncols), C_SLP_BLNK)
            outarray[slope['minimal'].astype(bool)] = C_SLP_MIN
            outarray[slope['moderate'].astype(bool)] = C_SLP_MOD
            outarray[slope['steep'].astype(bool)] = C_SLP_STP
            slope_f.GetRasterBand(1).WriteArray(outarray, xoff=x, yoff=y)

            outarray = np.full((nrows, ncols), C_LUS_BLNK)
            outarray[land_use['forest'].astype(bool)] = C_LUS_FRST
            outarray[land_use['cropland_rainfed'].astype(bool)] = C_LUS_CRRF
            outarray[land_use['cropland_irrigated'].astype(bool)] = C_LUS_CRIR
            outarray[land_use['grassland'].astype(bool)] = C_LUS_GRSS
            outarray[land_use['bare'].astype(bool)] = C_LUS_BARE
            outarray[land_use['urban'].astype(bool)] = C_LUS_URBN
            outarray[land_use['water'].astype(bool)] = C_LUS_WATR
            outarray[land_use['ice'].astype(bool)] = C_LUS_ICE
            land_use_f.GetRasterBand(1).WriteArray(outarray, xoff=x, yoff=y)

            outarray = np.full((nrows, ncols), C_SLP_BLNK)
            outarray[soil_health['prime'].astype(bool)] = C_SLH_GOOD
            outarray[soil_health['good'].astype(bool)] = C_SLH_MRGN
            outarray[soil_health['marginal'].astype(bool)] = C_SLH_POOR
            outarray[soil_health['barren'].astype(bool)] = C_SLH_BARE
            outarray[soil_health['water'].astype(bool)] = C_SLH_WATR
            soil_health_f.GetRasterBand(1).WriteArray(outarray, xoff=x, yoff=y)

    aez_f = None
    slope_f = None
    land_use_f = None
    soil_health_f = None


def produce_PNGs():
    subprocess.run(args=['gdal_translate', '-of', 'png', '-expand', 'rgb', '-outsize', '1%', '0',
        './results/AEZ.tif', './results/AEZ_small.png'])
    subprocess.run(args=['gdal_translate', '-of', 'png', '-expand', 'rgb', '-outsize', '1%', '0',
        './results/Slope.tif', './results/Slope_small.png'])
    subprocess.run(args=['gdal_translate', '-of', 'png', '-expand', 'rgb', '-outsize', '1%', '0',
        './results/SoilHealth.tif', './results/SoilHealth_small.png'])
    subprocess.run(args=['gdal_translate', '-of', 'png', '-expand', 'rgb', '-outsize', '1%', '0',
        './results/LandUse.tif', './results/LandUse_small.png'])


if __name__ == '__main__':
    signal.signal(signal.SIGUSR1, start_pdb)
    os.environ['GDAL_CACHEMAX'] = '128'
    produce_CSV()
    produce_GeoTIFF()
    produce_PNGs()
