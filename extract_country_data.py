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


pd.set_option("display.max_rows", 500)
pd.set_option("display.max_columns", 40)
pd.options.display.float_format = '{:.2f}'.format
osgeo.gdal.PushErrorHandler("CPLQuietErrorHandler")
np.set_printoptions(threshold=sys.maxsize)



class KGlookup:
    """Lookup table of pixel color to Köppen-Geiger class.

       Mappings come from legend.txt file in ZIP archive from
       https://www.nature.com/articles/sdata2018214.pdf at http://www.gloh2o.org/koppen/
    """
    kg_colors = {
        (  0,   0, 255): 'Af',  (  0, 120, 255): 'Am',  ( 70, 170, 250): 'Aw',
        (255,   0,   0): 'BWh', (255, 150, 150): 'BWk', (245, 165,   0): 'BSh',
        (255, 220, 100): 'BSk',
        (255, 255,   0): 'Csa', (200, 200,   0): 'Csb', (150, 150,   0): 'Csc',
        (150, 255, 150): 'Cwa', (100, 200, 100): 'Cwb', ( 50, 150,  50): 'Cwc',
        (200, 255,  80): 'Cfa', (100, 255,  80): 'Cfb', ( 50, 200,   0): 'Cfc',
        (255,   0, 255): 'Dsa', (200,   0, 200): 'Dsb', (150,  50, 150): 'Dsc',
        (150, 100, 150): 'Dsd', (170, 175, 255): 'Dwa', ( 90, 120, 220): 'Dwb',
        ( 75,  80, 180): 'Dwc', ( 50,   0, 135): 'Dwd', (  0, 255, 255): 'Dfa',
        ( 55, 200, 255): 'Dfb', (  0, 125, 125): 'Dfc', (  0,  70,  95): 'Dfd',
        (178, 178, 178): 'ET',  (102, 102, 102): 'EF',
        }

    def __init__(self, mapfilename, maskdim='1km'):
        self.maskdim = maskdim
        self.img = osgeo.gdal.Open(mapfilename, osgeo.gdal.GA_ReadOnly)
        self.band = self.img.GetRasterBand(1)
        self.ctable = self.band.GetColorTable()

    def km2(self, x, y, ncols, nrows, maskblock, km2block, df, admin):
        block = self.band.ReadAsArray(x, y, ncols, nrows)
        masked = np.ma.masked_array(block, mask=np.logical_not(maskblock))
        for label in np.unique(masked):
            if label is np.ma.masked:
                continue
            r, g, b, a = self.ctable.GetColorEntry(int(label))
            color = (r, g, b)
            if color == (255, 255, 255) or color == (0, 0, 0):
                # blank pixel == masked off, just skip it.
                continue
            typ = self.kg_colors[color]
            df.loc[admin, typ] += km2block[masked == label].sum()

    def get_columns(self):
        return self.kg_colors.values()


class ESA_LC_lookup:
    """Pixel color to Land Cover class in ESACCI-LC-L4-LCCS-Map-300m-P1Y-2015-v2.0.7.tif

       There are legends of LCCS<->color swatch in both
       http://maps.elie.ucl.ac.be/CCI/viewer/download/ESACCI-LC-QuickUserGuide-LC-Maps_v2-0-7.pdf
       and section 9.1 of http://maps.elie.ucl.ac.be/CCI/viewer/download/ESACCI-LC-Ph2-PUGv2_2.0.pdf
       but these were generated from Microsoft Word documents and contain embedded color profiles
       for color correction, meaning that what is displayed on the screen (and to any sort of
       Digital Color Meter tool) have been shifted and do not match the original colors. Do not
       attempt to use the color legend in these files.

       There is a table of RGB to LCCS values in
       http://maps.elie.ucl.ac.be/CCI/viewer/download/ESACCI-LC-Legend.csv
       however: the GeoTIFF file as shipped is greyscale with no color table. Each pixel is 8 bits
       not because it is looked up in a color table, it is 8 bits because it has been converted to
       greyscale. The authors appear to have carefully chosen the RGB values such that when
       converted to greyscale, LCCS class 10 will have a grey value of 10, LCCS class 11 will have
       a grey value of 11, and so on.

       So we don't need a lookup table, greyscale absolute values directly equal the LCCS class."""

    def __init__(self, mapfilename, maskdim='333m'):
        self.maskdim = maskdim
        self.img = osgeo.gdal.Open(mapfilename, osgeo.gdal.GA_ReadOnly)
        self.band = self.img.GetRasterBand(1)

    def km2(self, x, y, ncols, nrows, maskblock, km2block, df, admin):
        block = self.band.ReadAsArray(x, y, ncols, nrows)
        masked = np.ma.masked_array(block, mask=np.logical_not(maskblock)).filled(-1)
        for label in np.unique(masked):
            if label is np.ma.masked or label == 0 or label == 255:
                continue
            df.loc[admin, label] += km2block[masked == label].sum()

    def get_columns(self):
        """Return list of LCCS classes present in this dataset."""
        return [10, 11, 12, 20, 30, 40, 50, 60, 61, 62, 70, 71, 72, 80, 81, 82, 90, 100, 110, 120,
                121, 122, 130, 140, 150, 151, 152, 153, 160, 170, 180, 190, 200, 201, 202, 210, 220]


class GeomorphoLookup:
    """Geomorpho90m pre-processed slope file in data/geomorpho90m/classified_*.tif.
       There is a band in the TIF for each slope class defined in GAEZ 3.0.
    """
    gaez_slopes = ["0-0.5%", "0.5-2%", "2-5%", "5-10%", "10-15%", "15-30%", "30-45%", ">45%"]

    def __init__(self, mapfilename, maskdim='1km'):
        self.maskdim = maskdim
        self.img = osgeo.gdal.Open(mapfilename, osgeo.gdal.GA_ReadOnly)

    def km2(self, x, y, ncols, nrows, maskblock, km2block, df, admin):
        for b in range(1, 9):
            block = self.img.GetRasterBand(b).ReadAsArray(x, y, ncols, nrows).astype(np.float)
            mask = np.logical_or(np.logical_not(maskblock), block == 127)
            masked = np.ma.masked_array(block, mask=mask, fill_value=0.0)
            typ = self.gaez_slopes[b - 1]
            df.loc[admin, typ] += (km2block * (masked / 100.0)).sum()

    def get_columns(self):
        """Return list of GAEZ slope classes."""
        return self.gaez_slopes


class WorkabilityLookup:
    """Workability TIF has been pre-processed, pixel values are workability class.
    """
    def __init__(self, mapfilename, maskdim='1km'):
        self.maskdim = maskdim
        self.img = osgeo.gdal.Open(mapfilename, osgeo.gdal.GA_ReadOnly)
        self.band = self.img.GetRasterBand(1)

    def km2(self, x, y, ncols, nrows, maskblock, km2block, df, admin):
        block = self.band.ReadAsArray(x, y, ncols, nrows)
        masked = np.ma.masked_array(block, mask=np.logical_not(maskblock))
        for label in np.unique(masked):
            if label is np.ma.masked or label == 0 or label == 255:
                # label 0 (black) == no land cover (like water), just skip it.
                continue
            df.loc[admin, label] += km2block[masked == label].sum()

    def get_columns(self):
        return range(1, 8)


def start_pdb(sig, frame):
    """Start PDB on a signal."""
    pdb.Pdb().set_trace(frame)


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


def process_map(lookupobj, csvfilename):
    """Produce a CSV file of areas per country from a dataset."""
    shapefilename = 'data/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp'
    df = pd.DataFrame(columns=lookupobj.get_columns(), dtype=float)
    df.index.name = 'Country'
    shapefile = osgeo.ogr.Open(shapefilename)
    assert shapefile.GetLayerCount() == 1
    layer = shapefile.GetLayerByIndex(0)

    for idx, feature in enumerate(layer):
        admin = admin_names.lookup(feature.GetField("ADMIN"))
        if admin is None:
            continue
        a3 = feature.GetField("SOV_A3")
        if admin not in df.index:
            df.loc[admin] = [0] * len(df.columns)

        print(f"Processing {admin:<41} #{a3}_{idx}")
        maskfilename = f"masks/{a3}_{idx}_{lookupobj.maskdim}_mask._tif"
        maskimg = osgeo.gdal.Open(maskfilename, osgeo.gdal.GA_ReadOnly)
        maskband = maskimg.GetRasterBand(1)
        x_siz = maskband.XSize
        y_siz = maskband.YSize
        x_blksiz, y_blksiz = maskband.GetBlockSize()
        for y in range(0, y_siz, y_blksiz):
            nrows = blklim(coord=y, blksiz=y_blksiz, totsiz=y_siz)
            for x in range(0, x_siz, x_blksiz):
                ncols = blklim(coord=x, blksiz=x_blksiz, totsiz=x_siz)
                if is_sparse(band=maskband, x=x, y=y, ncols=ncols, nrows=nrows):
                    # sparse hole in image, no data to process
                    continue

                maskblock = maskband.ReadAsArray(x, y, ncols, nrows)
                km2block = km2_block(nrows=nrows, ncols=ncols, y_off=y, img=maskimg)
                lookupobj.km2(x=x, y=y, ncols=ncols, nrows=nrows, maskblock=maskblock,
                              km2block=km2block, df=df, admin=admin)
    outputfilename = os.path.join('results', csvfilename)
    df.sort_index(axis='index').to_csv(outputfilename, float_format='%.2f')


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
            nrows = blklim(coord=y, blksiz=y_blksiz, totsiz=y_siz)
            for x in range(0, x_siz, x_blksiz):
                ncols = blklim(coord=x, blksiz=x_blksiz, totsiz=x_siz)
                if is_sparse(band=mask_band, x=x, y=y, ncols=ncols, nrows=nrows):
                    # sparse hole in image, no data to process
                    continue

                mask_blk = mask_band.ReadAsArray(x, y, ncols, nrows)
                k = km2_block(nrows=nrows, ncols=ncols, y_off=y, img=maskimg)
                k[np.logical_not(mask_blk)] = 0.0
                km2_blk = (np.repeat(np.repeat(k, 3, axis=1), 3, axis=0)) / 9.0

                k = kg_band.ReadAsArray(x, y, ncols, nrows)
                kg_blk = np.repeat(np.repeat(k, 3, axis=1), 3, axis=0)
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

                s = sl_band.ReadAsArray(x, y, ncols, nrows)
                sl_blk = np.repeat(np.repeat(s, 3, axis=1), 3, axis=0)
                slope = {}
                slope['minimal'] = sl_blk < 8.0
                slope['moderate'] = np.logical_and(sl_blk >= 8.0, sl_blk < 30.0)
                slope['steep'] = sl_blk >= 30.0

                lc_blk = lc_band.ReadAsArray(3*x, 3*y, 3*ncols, 3*nrows)
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

                w = wk_band.ReadAsArray(x, y, ncols, nrows)
                wk_blk = np.repeat(np.repeat(w, 3, axis=1), 3, axis=0)
                soil_health = {}
                soil_health['prime'] = (wk_blk == 1)
                soil_health['good'] = (wk_blk == 2)
                soil_health['marginal'] = np.logical_or(wk_blk == 3, wk_blk == 4)
                soil_health['bare'] = np.logical_or(wk_blk == 5, wk_blk == 6)
                soil_health['water'] = (wk_blk == 7)

                for tmr in tmr_names:
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
    df.sort_index(axis='index').to_csv(csvfilename, float_format='%.2f')


if __name__ == '__main__':
    signal.signal(signal.SIGUSR1, start_pdb)
    os.environ['GDAL_CACHEMAX'] = '128'

    parser = argparse.ArgumentParser(description='Process GeoTIFF datasets for Project Drawdown')
    parser.add_argument('--lc', default=False, required=False,
                        action='store_true', help='process land cover')
    parser.add_argument('--kg', default=False, required=False,
                        action='store_true', help='process Köppen-Geiger')
    parser.add_argument('--sl', default=False, required=False,
                        action='store_true', help='process slope')
    parser.add_argument('--wk', default=False, required=False,
                        action='store_true', help='process workability')
    parser.add_argument('--aez', default=False, required=False,
                        action='store_true', help='process AEZ')
    parser.add_argument('--all', default=False, required=False,
                        action='store_true', help='process all')
    args = parser.parse_args()

    processed = False
    shapefilename = 'data/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp'

    if args.lc or args.all:
        land_cover_files = [
                ('data/ucl_elie/ESACCI-LC-L4-LCCS-Map-300m-P1Y-2015-v2.0.7.tif', 'Land-Cover-by-country.csv'),
                ('data/ucl_elie/ESACCI-LC-L4-LCCS-Map-300m-P1Y-2014-v2.0.7.tif', 'Land-Cover-by-country-2014.csv'),
                ('data/ucl_elie/ESACCI-LC-L4-LCCS-Map-300m-P1Y-2013-v2.0.7.tif', 'Land-Cover-by-country-2013.csv'),
                ('data/ucl_elie/ESACCI-LC-L4-LCCS-Map-300m-P1Y-2012-v2.0.7.tif', 'Land-Cover-by-country-2012.csv'),
                ('data/ucl_elie/ESACCI-LC-L4-LCCS-Map-300m-P1Y-2011-v2.0.7.tif', 'Land-Cover-by-country-2011.csv'),
                ('data/ucl_elie/ESACCI-LC-L4-LCCS-Map-300m-P1Y-2010-v2.0.7.tif', 'Land-Cover-by-country-2010.csv'),
                ('data/ucl_elie/ESACCI-LC-L4-LCCS-Map-300m-P1Y-2009-v2.0.7.tif', 'Land-Cover-by-country-2009.csv'),
                ('data/ucl_elie/ESACCI-LC-L4-LCCS-Map-300m-P1Y-2008-v2.0.7.tif', 'Land-Cover-by-country-2008.csv')
                ]
        for (mapfilename, csvfilename) in land_cover_files:
            if not os.path.exists(mapfilename):
                print(f"Skipping missing {mapfilename}")
                continue
            print(mapfilename)
            lookupobj = ESA_LC_lookup(mapfilename)
            process_map(lookupobj=lookupobj, csvfilename=csvfilename)
            print('\n')
        processed = True

    if args.kg or args.all:
        mapfilename = 'data/Beck_KG_V1/Beck_KG_V1_present_0p0083.tif'
        csvfilename = 'Köppen-Geiger-present-by-country.csv'
        print(mapfilename)
        lookupobj = KGlookup(mapfilename)
        process_map(lookupobj=lookupobj, csvfilename=csvfilename)
        print('\n')

        mapfilename = 'data/Beck_KG_V1/Beck_KG_V1_future_0p0083.tif'
        csvfilename = 'Köppen-Geiger-future-by-country.csv'
        print(mapfilename)
        lookupobj = KGlookup(mapfilename)
        process_map(lookupobj=lookupobj, csvfilename=csvfilename)
        print('\n')
        processed = True

    if args.sl or args.all:
        mapfilename = 'data/geomorpho90m/classified_slope_merit_dem_1km_s0..0cm_2018_v1.0.tif'
        csvfilename = 'Slope-by-country.csv'
        print(mapfilename)
        lookupobj = GeomorphoLookup(mapfilename=mapfilename)
        process_map(lookupobj=lookupobj, csvfilename=csvfilename)
        print('\n')
        processed = True

    if args.wk or args.all:
        mapfilename = 'data/FAO/workability_FAO_sq7_1km.tif'
        csvfilename = 'Workability-by-country.csv'
        print(mapfilename)
        lookupobj = WorkabilityLookup(mapfilename)
        process_map(lookupobj=lookupobj, csvfilename=csvfilename)
        print('\n')
        processed = True

    if args.aez or args.all:
        process_aez()
        processed = True

    if not processed:
        print('Select one of:')
        print('\t-lc  : Land Cover')
        print('\t-kg  : Köppen-Geiger')
        print('\t-sl  : Slope')
        print('\t-wk  : Workability')
        print('\t-aez : AEZ')
        print('\t-all')
        sys.exit(1)
