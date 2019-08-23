# A script to rasterise a shapefile to the same projection & pixel resolution as a reference image.
import os.path
import tempfile
from osgeo import ogr, gdal

shapefile = 'ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp'
RefImage = 'Beck_KG_V1/Beck_KG_V1_present_conf_0p083.tif'
OutputImage = 'Result.tif'

##########################################################
# Get projection info from reference image
Image = gdal.Open(RefImage, gdal.GA_ReadOnly)

# Open Shapefile
Shapefile = ogr.Open(shapefile)
assert Shapefile.GetLayerCount() == 1
layer = Shapefile.GetLayerByIndex(0)

for feature in layer:
    sovereignty = feature.GetField("SOVEREIGNT")

    driver = ogr.GetDriverByName("ESRI Shapefile")
    tmpfile = tempfile.NamedTemporaryFile(suffix='.shp')
    if os.path.exists(tmpfile.name):
        driver.DeleteDataSource(tmpfile.name)

    outDataSource = driver.CreateDataSource(tmpfile.name)
    outLayer = outDataSource.CreateLayer("feature", geom_type=ogr.wkbPolygon)
    outLayer.CreateField(ogr.FieldDefn("SOVEREIGNT", ogr.OFTString))
    new_feat = ogr.Feature(outLayer.GetLayerDefn())
    geom = feature.GetGeometryRef()
    new_feat.SetGeometry(geom)
    new_feat.SetField("SOVEREIGNT", sovereignty)
    outLayer.CreateFeature(new_feat)
    new_feat = None
    outDataSource = None
    outLayer = None

    outDataSource = driver.Open(tmpfile.name, 0)
    outLayer = outDataSource.GetLayer()

    # Rasterise
    print(f"Rasterising shapefile for {str(sovereignty)}...")
    datatype = gdal.GDT_Byte
    Output = gdal.GetDriverByName('GTiff').Create(OutputImage, Image.RasterXSize,
            Image.RasterYSize, 1, datatype, options=['COMPRESS=DEFLATE'])
    Output.SetProjection(Image.GetProjectionRef())
    Output.SetGeoTransform(Image.GetGeoTransform()) 

    # Write data to band 1
    Band = Output.GetRasterBand(1)
    Band.SetNoDataValue(0)
    print("1")
    gdal.RasterizeLayer(Output, [1], outLayer, options=['ALL_TOUCHED=TRUE,ATTRIBUTE=SOVEREIGNT'])
    print("2")

    # Close datasets
    Band = None
    Output = None
    Image = None
    Shapefile = None
    outDataSource = None
    outLayer = None

    print("Done.")
    break
