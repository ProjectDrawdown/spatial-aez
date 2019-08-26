# Extract counts of each Köppen-Geiger class for each country, exported to CSV.
import collections
import math
import os.path
import shutil
import subprocess
import tempfile

import osgeo.gdal
import osgeo.gdal_array
import osgeo.ogr

import pandas as pd

pd.set_option("display.max_rows", 500)
pd.set_option("display.max_columns", 40)
osgeo.gdal.PushErrorHandler("CPLQuietErrorHandler")



# Lookup table of pixel color to Köppen-Geiger class.
#
# Mappings come from legend.txt file in ZIP archive from
# https://www.nature.com/articles/sdata2018214.pdf at http://www.gloh2o.org/koppen/
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


def rasterize_shapefile(worldimage, shpfile, outfile):
    """Rasterize a shapefile to TIFF."""
    driver = osgeo.ogr.GetDriverByName("ESRI Shapefile")
    data_source = driver.Open(shpfile, 0)
    layer = data_source.GetLayer()
    datatype = osgeo.gdal.GDT_Byte
    output = osgeo.gdal.GetDriverByName('GTiff').Create(outfile, worldimage.RasterXSize,
            worldimage.RasterYSize, 1, datatype, options=['COMPRESS=DEFLATE'])
    output.SetProjection(worldimage.GetProjectionRef())
    output.SetGeoTransform(worldimage.GetGeoTransform()) 
    band = output.GetRasterBand(1)
    band.SetNoDataValue(0)
    osgeo.gdal.RasterizeLayer(output, [1], layer, options=['ATTRIBUTE=SOVEREIGNT'])


def one_feature_shapefile(worldmapname, worldimage, a3, idx, feature, tmpdir, srs):
    """Make a new shapefile, to hold the one Feature we're looking at."""
    driver = osgeo.ogr.GetDriverByName("ESRI Shapefile")
    shpfile = os.path.join(tmpdir, f'{a3}_{idx}_feature_mask.shp')
    data_source = driver.CreateDataSource(shpfile)
    layer = data_source.CreateLayer("feature", geom_type=osgeo.ogr.wkbPolygon, srs=srs)
    new_feat = osgeo.ogr.Feature(layer.GetLayerDefn())
    geom = feature.GetGeometryRef()
    new_feat.SetGeometry(geom)
    layer.CreateFeature(new_feat)

    # Close datasets. GDAL needs this as it implements some of the work in the destructor.
    new_feat = None
    data_source = None
    layer = None

    # Rasterise the shapefile just created. We don't strictly need this, but useful for debugging.
    outfile = os.path.join(tmpdir, f'{a3}_{idx}_feature_mask.tif')
    rasterize_shapefile(worldimage=worldimage, shpfile=shpfile, outfile=outfile)

    # Apply shapefile as a mask, and crop to the size of the mask
    clippedfile = os.path.join(tmpdir, f'{a3}_{idx}_feature.tif')
    result = osgeo.gdal.Warp(clippedfile, worldmapname, cutlineDSName=shpfile, cropToCutline=True,
            warpOptions = ['CUTLINE_ALL_TOUCHED=TRUE'])
    if result is not None:
        return clippedfile


def update_df_from_image(filename, sovereignty, ctable, df):
    """Count K-G classes by pixel, add to df."""
    img = osgeo.gdal.Open(filename, osgeo.gdal.GA_ReadOnly)
    xmin, xsiz, xrot, ymin, yrot, ysiz = img.GetGeoTransform()
    img = None
    arr = osgeo.gdal_array.LoadFile(filename)
    yrad = math.radians(abs(ysiz))
    y = math.radians(ymin)
    for row in arr:
        km2 = (111.132954 * abs(ysiz)) * (111.132954 * xsiz * math.cos(y))
        counts = collections.Counter(row)
        for (label, count) in counts.items():
            r, g, b, a = ctable.GetColorEntry(int(label))
            color = (r, g, b)
            if color == (255, 255, 255):
                # blank pixel == masked off, just skip it.
                continue
            kg_class = kg_colors[color]
            df.loc[sovereignty, kg_class] += (count * km2)
        y -= yrad


def main(shapefilename, worldmapname, tmpdir, csvfilename):
    df = pd.DataFrame(columns=kg_colors.values())
    df.index.name = 'Country'
    shapefile = osgeo.ogr.Open(shapefilename)
    assert shapefile.GetLayerCount() == 1
    layer = shapefile.GetLayerByIndex(0)
    srs = layer.GetSpatialRef()
    worldimage = osgeo.gdal.Open(worldmapname, osgeo.gdal.GA_ReadOnly)
    ctable = worldimage.GetRasterBand(1).GetColorTable()

    for idx, feature in enumerate(layer):
        sovereignty = feature.GetField("SOVEREIGNT")
        a3 = feature.GetField("SOV_A3")
        if not sovereignty in df.index:
            df.loc[sovereignty] = [0] * len(df.columns)

        clippedfile = one_feature_shapefile(worldmapname=worldmapname, worldimage=worldimage,
                a3=a3, idx=idx, feature=feature, tmpdir=tmpdir, srs=srs)
        if clippedfile:
            update_df_from_image(filename=clippedfile, sovereignty=sovereignty,
                    ctable=ctable, df=df)
        else:
            print(f"{sovereignty} feature #{idx} is empty, skipping.")
        if idx > 4:
            break

    df.sort_index(axis='index').to_csv(csvfilename, float_format='%.2f')


if __name__ == '__main__':
    shapefilename = 'ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp'
    worldmapname = 'Beck_KG_V1/Beck_KG_V1_present_0p0083.tif'
    tmpdirobj = tempfile.TemporaryDirectory()
    csvfilename = 'Köppen-Geiger-by-country.csv'
    main(shapefilename=shapefilename, worldmapname=worldmapname, tmpdir=tmpdirobj.name,
            csvfilename=csvfilename)
