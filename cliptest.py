import os.path
import time

import osgeo.gdal
import osgeo.ogr

def rasterize_shapefile(img, shapefilename, outfile):
    """Rasterize a shapefile to TIFF."""
    print('opening shapefile')
    driver = osgeo.ogr.GetDriverByName("ESRI Shapefile")
    shapefile = driver.Open(shapefilename, 0)
    layer = shapefile.GetLayerByIndex(0)
    srs = layer.GetSpatialRef()
    feature = layer[48]   # Russia
    geom = feature.GetGeometryRef()
    minX, maxX, minY, maxY = geom.GetEnvelope()

    print('Creating new shapefile')
    new_data_source = driver.CreateDataSource('result.shp')
    new_layer = new_data_source.CreateLayer("feature", geom_type=osgeo.ogr.wkbPolygon, srs=srs)
    new_feat = osgeo.ogr.Feature(layer.GetLayerDefn())
    new_feat.SetGeometry(geom)
    new_layer.CreateFeature(new_feat)

    # Close datasets. GDAL needs this as it implements some of the work in the destructor.
    new_feat = None
    new_data_source = None
    new_layer = None

    print('Rasterizing')
    data_source = driver.Open('result.shp', 0)
    new_layer = data_source.GetLayer()

    # Russia (feature #48): DEFLATE: 11 Megs, LZW: 46 Megs.
    # w/ NBITS=1, Russia ZSTD: 2.3 Megs, DEFLATE: 3.8 Megs, LZW: 15 Megs, PACKBITS: 67 Megs
    output = osgeo.gdal.GetDriverByName('GTiff').Create(
            outfile, img.RasterXSize, img.RasterYSize, 1, osgeo.gdal.GDT_Byte,
            options=['NBITS=1', 'COMPRESS=ZSTD', 'TILED=YES', 'NUM_THREADS=2', 'SPARSE_OK=TRUE'])
    output.SetProjection(img.GetProjectionRef())
    output.SetGeoTransform(img.GetGeoTransform())
    options = osgeo.gdal.RasterizeOptions(outputBounds=[minX, minY, maxX, maxY], outputSRS=srs)
    osgeo.gdal.RasterizeLayer(output, [1], new_layer)


#for filename in ['data/ucl_elie/ESACCI-LC-L4-LCCS-Map-300m-P1Y-2015-v2.0.7.tif',
#                 'data/Beck_KG_V1/Beck_KG_V1_present_0p0083.tif',
#                 'data/Beck_KG_V1/Beck_KG_V1_future_0p0083.tif',
#                 'data/geomorpho90m/classified_slope_merit_dem_250m_s0..0cm_2018_v1.0.tif',
#                 'data/FAO/workability_FAO_sq7_10km.tif']:

if __name__ == '__main__':
    if os.path.exists('result.tif'):
        img = osgeo.gdal.Open('result.tif', osgeo.gdal.GA_ReadOnly)
        band = img.GetRasterBand(1)
        x_blksiz, y_blksiz = band.GetBlockSize()
        x_siz = band.XSize
        y_siz = band.YSize
        status_0 = status_1 = status_u = 0
        for y_off in range(0, y_siz, y_blksiz):
            if y_off + y_blksiz < y_siz:
                rows = y_blksiz
            else:
                rows = y_siz - y_off
            for x_off in range(0, x_siz, x_blksiz):
                if x_off + x_blksiz < x_siz:
                    cols = x_blksiz
                else:
                    cols = x_siz - x_off

                (flags, pct) = band.GetDataCoverageStatus(x_off, y_off, cols, rows)
                if flags != osgeo.gdal.GDAL_DATA_COVERAGE_STATUS_DATA:
                    status_u += 1
                elif pct == 100.0:
                    status_1 += 1
                else:
                    status_0 += 1
        print(f"0: {status_0}  1: {status_1} unk: {status_u}")

    else:
        filename = 'data/ucl_elie/ESACCI-LC-L4-LCCS-Map-300m-P1Y-2015-v2.0.7.tif'
        print('Opening' + filename)
        img = osgeo.gdal.Open(filename, osgeo.gdal.GA_ReadOnly)
        shapefilename = 'data/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp'
        rasterize_shapefile(img=img, shapefilename=shapefilename, outfile='result.tif')
