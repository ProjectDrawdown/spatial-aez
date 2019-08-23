import os
from osgeo import ogr

filename = "ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp"
driver = ogr.GetDriverByName('ESRI Shapefile')
data = driver.Open(filename, 0) # 0 means read-only. 1 means writeable.

# Check to see if shapefile is found.
if data is None:
    print(f'Could not open {filename}')
else:
    layer = data.GetLayer()
    featureCount = layer.GetFeatureCount()
    print(f"Number of features in {os.path.basename(filename)} : {featureCount}")
