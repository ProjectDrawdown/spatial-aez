# Extract counts of each Köppen-Geiger class for each country, exported to CSV.
import collections
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


shapefilename = 'ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp'
worldmapname = 'Beck_KG_V1/Beck_KG_V1_present_0p0083.tif'
worldimage = osgeo.gdal.Open(worldmapname, osgeo.gdal.GA_ReadOnly)
ctable = worldimage.GetRasterBand(1).GetColorTable()
csvfilename = 'Köppen-Geiger-by-country.csv'

shapefile = osgeo.ogr.Open(shapefilename)
assert shapefile.GetLayerCount() == 1
layer = shapefile.GetLayerByIndex(0)
srs = layer.GetSpatialRef()


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

def rgb_to_kg(color):
    if color == (255, 255, 255):
        return None
    return kg_colors[color]

df = pd.DataFrame(columns=kg_colors.values())
df.index.name = 'Country'
tmpdirobj = tempfile.TemporaryDirectory()
tmpdir = tmpdirobj.name


for idx, feature in enumerate(layer):
    sovereignty = feature.GetField("SOVEREIGNT")
    a3 = feature.GetField("SOV_A3")
    if df.get(sovereignty, None) is None:
        df.loc[sovereignty] = [0] * len(df.columns)

    # Make a new shapefile, to hold the one Feature we're looking at in this loop
    driver = osgeo.ogr.GetDriverByName("ESRI Shapefile")
    shpfile = os.path.join(tmpdir, f'{a3}_feature_{idx}.shp')

    # make a new Layer for this one Feature
    outDataSource = driver.CreateDataSource(shpfile)
    outLayer = outDataSource.CreateLayer("feature", geom_type=osgeo.ogr.wkbPolygon, srs=srs)
    outLayer.CreateField(osgeo.ogr.FieldDefn("SOVEREIGNT", osgeo.ogr.OFTString))
    new_feat = osgeo.ogr.Feature(outLayer.GetLayerDefn())
    geom = feature.GetGeometryRef()
    new_feat.SetGeometry(geom)
    new_feat.SetField("SOVEREIGNT", sovereignty)
    outLayer.CreateFeature(new_feat)
    new_feat = None
    outDataSource = None
    outLayer = None
    outDataSource = driver.Open(shpfile, 0)
    outLayer = outDataSource.GetLayer()

    # Rasterise the shapefile we just created
    if False:
        datatype = osgeo.gdal.GDT_Byte
        shptiffile = os.path.join(tmpdir, f'{a3}_feature_shp_{idx}.tif')
        Output = osgeo.gdal.GetDriverByName('GTiff').Create(shptiffile, worldimage.RasterXSize,
                worldimage.RasterYSize, 1, datatype, options=['COMPRESS=DEFLATE'])
        Output.SetProjection(worldimage.GetProjectionRef())
        Output.SetGeoTransform(worldimage.GetGeoTransform()) 
        Band = Output.GetRasterBand(1)
        Band.SetNoDataValue(0)
        osgeo.gdal.RasterizeLayer(Output, [1], outLayer,
                options=['ALL_TOUCHED=TRUE,ATTRIBUTE=SOVEREIGNT'])

    # Close datasets. GDAL needs this as it implements some of the work in the destructor.
    Band = None
    Output = None
    outDataSource = None
    outLayer = None

    # Apply shapefile as a mask, and crop to the size of the mask
    clippedfile = os.path.join(tmpdir, f'{a3}_feature_{idx}.tif')
    result = osgeo.gdal.Warp(clippedfile, worldmapname, cutlineDSName=shpfile, cropToCutline=True)
    if result is not None:
        # have to discard result to let GDAL run destructors, otherwise clippedfile
        # will only be partially written out when the gdal_array.LoadFile runs.
        result = None
        counts = collections.Counter(osgeo.gdal_array.LoadFile(clippedfile).flatten())
        for (label, count) in counts.items():
            r, g, b, a = ctable.GetColorEntry(int(label))
            color = (r, g, b)
            if color == (255, 255, 255):
                # blank pixel == masked off, just skip it.
                continue
            kg_class = kg_colors[color]
            df.loc[sovereignty, kg_class] += count
    else:
        print(f"{sovereignty} feature #{idx} is empty, skipping.")



df.sort_index(axis='index', to_csv(csvfilename)

# Close the original World-level shapefile and worldimage.
shapefile = None
worldimage = None
