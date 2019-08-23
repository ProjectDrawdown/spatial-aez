# A script to rasterise a shapefile to the same projection & pixel resolution as a reference image.
import os.path
import subprocess
import tempfile

import osgeo.gdal
import osgeo.ogr

shapefile = 'ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp'
imagename = 'Beck_KG_V1/Beck_KG_V1_present_conf_0p083.tif'
OutputImage = 'Result.tif'

##########################################################
# Get projection info from reference image
Image = osgeo.gdal.Open(imagename, osgeo.gdal.GA_ReadOnly)

# Open Shapefile
Shapefile = osgeo.ogr.Open(shapefile)
assert Shapefile.GetLayerCount() == 1
layer = Shapefile.GetLayerByIndex(0)

for feature in layer:
    sovereignty = feature.GetField("SOVEREIGNT")

    # Make a new shapefile, to hold the one Feature we're looking at in this loop
    driver = osgeo.ogr.GetDriverByName("ESRI Shapefile")
    shpfile = tempfile.NamedTemporaryFile(suffix='.shp')
    if os.path.exists(shpfile.name):
        driver.DeleteDataSource(shpfile.name)

    # make a new Layer for this one Feature
    outDataSource = driver.CreateDataSource(shpfile.name)
    outLayer = outDataSource.CreateLayer("feature", geom_type=osgeo.ogr.wkbPolygon,
            srs=layer.GetSpatialRef())
    outLayer.CreateField(osgeo.ogr.FieldDefn("SOVEREIGNT", osgeo.ogr.OFTString))
    new_feat = osgeo.ogr.Feature(outLayer.GetLayerDefn())
    geom = feature.GetGeometryRef()
    new_feat.SetGeometry(geom)
    new_feat.SetField("SOVEREIGNT", sovereignty)
    outLayer.CreateFeature(new_feat)
    new_feat = None
    outDataSource = None
    outLayer = None
    outDataSource = driver.Open(shpfile.name, 0)
    outLayer = outDataSource.GetLayer()

    # Rasterise the shapefile we just created
    if False:
        print(f"Rasterising shapefile for {str(sovereignty)}...")
        datatype = osgeo.gdal.GDT_Byte
        Output = osgeo.gdal.GetDriverByName('GTiff').Create(OutputImage, Image.RasterXSize,
                Image.RasterYSize, 1, datatype, options=['COMPRESS=DEFLATE'])
        Output.SetProjection(Image.GetProjectionRef())
        Output.SetGeoTransform(Image.GetGeoTransform()) 
        Band = Output.GetRasterBand(1)
        Band.SetNoDataValue(0)
        osgeo.gdal.RasterizeLayer(Output, [1], outLayer,
                options=['ALL_TOUCHED=TRUE,ATTRIBUTE=SOVEREIGNT'])

    geom = feature.GetGeometryRef()
    minX, maxX, minY, maxY = geom.GetEnvelope()
    bbox = (minX, maxY, maxX, minY)
    clippedfile = tempfile.NamedTemporaryFile(suffix='.tif')

    # Apply shapefile as a mask
    subprocess.call(['gdalwarp', '-cutline', shpfile.name,
        '-te', str(minX), str(minY), str(maxX), str(maxY),
        imagename, clippedfile.name])


    # Close datasets. GDAL needs this as it implements some of the work in the destructor.
    Band = None
    Output = None
    outDataSource = None
    outLayer = None
    shpfile = None
    clippedfile = None

    print("Done.")
    break


# Close the original World-level shapefile and Image.
Shapefile = None
Image = None
