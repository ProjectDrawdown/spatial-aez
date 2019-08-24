# Extract counts of each Köppen-Geiger class for each country, exported to CSV.
import collections
import os.path
import subprocess
import tempfile

import osgeo.gdal
import osgeo.gdal_array
import osgeo.ogr

shapefilename = 'ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp'
worldmapname = 'Beck_KG_V1/Beck_KG_V1_present_0p083.tif'
worldimage = osgeo.gdal.Open(worldmapname, osgeo.gdal.GA_ReadOnly)
ctable = worldimage.GetRasterBand(1).GetColorTable()

# Open shapefile
shapefile = osgeo.ogr.Open(shapefilename)
assert shapefile.GetLayerCount() == 1
layer = shapefile.GetLayerByIndex(0)
srs = layer.GetSpatialRef()

for feature in layer:
    sovereignty = feature.GetField("SOVEREIGNT")
    a3 = feature.GetField("SOV_A3")

    # Make a new shapefile, to hold the one Feature we're looking at in this loop
    driver = osgeo.ogr.GetDriverByName("ESRI Shapefile")
    shpfile = tempfile.NamedTemporaryFile(prefix=f'{a3}_', suffix='.shp')
    if os.path.exists(shpfile.name):
        driver.DeleteDataSource(shpfile.name)

    # make a new Layer for this one Feature
    outDataSource = driver.CreateDataSource(shpfile.name)
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
    outDataSource = driver.Open(shpfile.name, 0)
    outLayer = outDataSource.GetLayer()

    # Rasterise the shapefile we just created, for debugging.
    if False:
        print(f"Rasterising shapefile for {str(sovereignty)}...")
        datatype = osgeo.gdal.GDT_Byte
        Output = osgeo.gdal.GetDriverByName('GTiff').Create('Result.tif', worldimage.RasterXSize,
                worldimage.RasterYSize, 1, datatype, options=['COMPRESS=DEFLATE'])
        Output.SetProjection(worldimage.GetProjectionRef())
        Output.SetGeoTransform(worldimage.GetGeoTransform()) 
        Band = Output.GetRasterBand(1)
        Band.SetNoDataValue(0)
        osgeo.gdal.RasterizeLayer(Output, [1], outLayer,
                options=['ALL_TOUCHED=TRUE,ATTRIBUTE=SOVEREIGNT'])

    geom = feature.GetGeometryRef()
    minX, maxX, minY, maxY = geom.GetEnvelope()
    bbox = (minX, maxY, maxX, minY)
    clippedfile = tempfile.NamedTemporaryFile(prefix=f'{a3}_', suffix='.tif')

    # Apply shapefile as a mask, and crop to the size of the mask
    subprocess.call(['gdalwarp', '-cutline', shpfile.name,
        '-te', str(minX), str(minY), str(maxX), str(maxY),
        worldmapname, clippedfile.name])

    counts = collections.Counter(osgeo.gdal_array.LoadFile(clippedfile.name).flatten())
    for (label, count) in counts.items():
        color = ctable.GetColorEntry(int(label))
        print(f'({color[0]}, {color[1]}, {color[2]}): {count}')

    # Close datasets. GDAL needs this as it implements some of the work in the destructor.
    Band = None
    Output = None
    outDataSource = None
    outLayer = None
    shpfile = None
    clippedfile = None

    print("Done.")


# Close the original World-level shapefile and worldimage.
shapefile = None
worldimage = None
