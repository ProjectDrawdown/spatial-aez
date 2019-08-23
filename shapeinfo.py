import os
from osgeo import ogr

daShapefile = "ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp"

driver = ogr.GetDriverByName('ESRI Shapefile')

dataSource = driver.Open(daShapefile, 0) # 0 means read-only. 1 means writeable.

# Check to see if shapefile is found.
if dataSource is None:
    print(f'Could not open {daShapefile}')
else:
    layer = dataSource.GetLayer()
    featureCount = layer.GetFeatureCount()
    print(f"Number of features in {os.path.basename(daShapefile)} :{featureCount}")
