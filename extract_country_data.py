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
np.seterr(all='raise')



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
    """Pixel color to Land Cover class in C3S-LC-L4-LCCS-Map-300m-P1Y-2018-v2.1.1.tif

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


class FaoSlopeLookup:
    """FAO GAEZ 3.0 slope files in data/FAO/GloSlopesCl*_30as.tif.
    """
    gaez_slopes = ["0-0.5%", "0.5-2%", "2-5%", "5-8%", "8-15%", "15-30%", "30-45%", ">45%"]

    def __init__(self, maskdim='1km'):
        self.maskdim = maskdim
        self.img = {}
        for i in range(1, 9):
            mapfilename = f"data/FAO/GloSlopesCl{i}_30as.tif"
            self.img[i] = osgeo.gdal.Open(mapfilename, osgeo.gdal.GA_ReadOnly)

    def km2(self, x, y, ncols, nrows, maskblock, km2block, df, admin):
        for i in range(1, 9):
            block = self.img[i].GetRasterBand(1).ReadAsArray(x, y, ncols, nrows).astype(np.float)
            mask = np.logical_or(np.logical_not(maskblock), block == 255)
            masked = np.ma.masked_array(block, mask=mask).filled(0.0)
            typ = self.gaez_slopes[i - 1]
            df.loc[admin, typ] += np.nansum(km2block * (masked / 100.0))

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


class DegradedLandLookup:
    """Binary indication of soil in LDPclass 1, 2, or 3."""
    def __init__(self, mapfilename, maskdim='1km'):
        self.maskdim = maskdim
        self.img = osgeo.gdal.Open(mapfilename, osgeo.gdal.GA_ReadOnly)
        self.band = self.img.GetRasterBand(1)

    def km2(self, x, y, ncols, nrows, maskblock, km2block, df, admin):
        block = self.band.ReadAsArray(x, y, ncols, nrows)
        masked = np.ma.masked_array(block, mask=np.logical_not(maskblock))
        for label in np.unique(masked):
            if label is np.ma.masked:
                continue
            if label == 0.0:
                df.loc[admin, "nondegraded"] += km2block[masked == label].sum()
            else:
                df.loc[admin, "degraded"] += km2block[masked == label].sum()

    def get_columns(self):
        return ["degraded", "nondegraded"]


def start_pdb(sig, frame):
    """Start PDB on a signal."""
    pdb.Pdb().set_trace(frame)


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
            nrows = geoutil.blklim(coord=y, blksiz=y_blksiz, totsiz=y_siz)
            for x in range(0, x_siz, x_blksiz):
                ncols = geoutil.blklim(coord=x, blksiz=x_blksiz, totsiz=x_siz)
                if geoutil.is_sparse(band=maskband, x=x, y=y, ncols=ncols, nrows=nrows):
                    # sparse hole in image, no data to process
                    continue

                maskblock = maskband.ReadAsArray(x, y, ncols, nrows)
                km2block = geoutil.km2_block(nrows=nrows, ncols=ncols, y_off=y, img=maskimg)
                lookupobj.km2(x=x, y=y, ncols=ncols, nrows=nrows, maskblock=maskblock,
                              km2block=km2block, df=df, admin=admin)
    outputfilename = os.path.join('results', csvfilename)
    df.sort_index(axis='index').to_csv(outputfilename, float_format='%.2f')
    return df


def output_by_region(df, csvfilename):
    regions = ['OECD90', 'Eastern Europe', 'Asia (Sans Japan)', 'Middle East and Africa',
            'Latin America', 'China', 'India', 'EU', 'USA']
    df_region = pd.DataFrame(0, index=regions, columns=df.columns.copy())
    df_region.index.name = 'Region'
    for country, row in df.iterrows():
        region = admin_names.region_mapping[country]
        if region is not None:
            df_region.loc[region, :] += row
    df_region.to_csv(csvfilename, float_format='%.2f')


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
    parser.add_argument('--dg', default=False, required=False,
                        action='store_true', help='process degraded land')
    parser.add_argument('--all', default=False, required=False,
                        action='store_true', help='process all')
    args = parser.parse_args()
    processed = False

    if args.lc or args.all:
        mapfilename = 'data/copernicus/C3S-LC-L4-LCCS-Map-300m-P1Y-2018-v2.1.1.tif'
        countrycsv = 'Land-Cover-by-country.csv'
        regioncsv = 'Land-Cover-by-region.csv'
        lookupobj = ESA_LC_lookup(mapfilename)
        df = process_map(lookupobj=lookupobj, csvfilename=countrycsv)
        output_by_region(df=df, csvfilename=regioncsv)
        print('\n')
        processed = True

    if args.kg or args.all:
        mapfilename = 'data/Beck_KG_V1/Beck_KG_V1_present_0p0083.tif'
        countrycsv = 'Köppen-Geiger-present-by-country.csv'
        regioncsv = 'Köppen-Geiger-present-by-region.csv'
        print(mapfilename)
        lookupobj = KGlookup(mapfilename)
        df = process_map(lookupobj=lookupobj, csvfilename=countrycsv)
        output_by_region(df=df, csvfilename=regioncsv)
        print('\n')

        mapfilename = 'data/Beck_KG_V1/Beck_KG_V1_future_0p0083.tif'
        countrycsv = 'Köppen-Geiger-future-by-country.csv'
        regioncsv = 'Köppen-Geiger-future-by-region.csv'
        print(mapfilename)
        lookupobj = KGlookup(mapfilename)
        df = process_map(lookupobj=lookupobj, csvfilename=countrycsv)
        output_by_region(df=df, csvfilename=regioncsv)
        print('\n')
        processed = True

    if args.sl or args.all:
        mapfilename = 'data/geomorpho90m/classified_slope_merit_dem_1km_s0..0cm_2018_v1.0.tif'
        countrycsv = 'Slope-by-country.csv'
        regioncsv = 'Slope-by-region.csv'
        print(mapfilename)
        lookupobj = GeomorphoLookup(mapfilename=mapfilename)
        df = process_map(lookupobj=lookupobj, csvfilename=countrycsv)
        output_by_region(df=df, csvfilename=regioncsv)
        print('\n')
        processed = True

        countrycsv = 'FAO-Slope-by-country.csv'
        regioncsv = 'FAO-Slope-by-region.csv'
        print('data/FAO/GloSlopesCl*_30as.tif')
        lookupobj = FaoSlopeLookup()
        df = process_map(lookupobj=lookupobj, csvfilename=countrycsv)
        output_by_region(df=df, csvfilename=regioncsv)
        print('\n')
        processed = True

    if args.wk or args.all:
        mapfilename = 'data/FAO/workability_FAO_sq7_1km.tif'
        countrycsv = 'Workability-by-country.csv'
        regioncsv = 'Workability-by-region.csv'
        print(mapfilename)
        lookupobj = WorkabilityLookup(mapfilename)
        df = process_map(lookupobj=lookupobj, csvfilename=countrycsv)
        output_by_region(df=df, csvfilename=regioncsv)
        print('\n')
        processed = True

    if not processed:
        print('Select one of:')
        print('\t-lc  : Land Cover')
        print('\t-kg  : Köppen-Geiger')
        print('\t-sl  : Slope')
        print('\t-wk  : Workability')
        print('\t-dg  : Degraded Land')
        print('\t-all')
        sys.exit(1)
