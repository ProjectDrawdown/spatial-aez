import os.path
import time

import numpy as np
import osgeo.gdal
import osgeo.ogr

def rasterize_shapefile(img, shapefilename, outfile):
    """Rasterize a shapefile to TIFF."""
    # Step 1: open the original Shapefile.
    shp_drv = osgeo.ogr.GetDriverByName("ESRI Shapefile")
    shapefile = shp_drv.Open(shapefilename, 0)
    layer = shapefile.GetLayerByIndex(0)
    srs = layer.GetSpatialRef()
    feature = layer[48]   # Russia
    geom = feature.GetGeometryRef()
    minX, maxX, minY, maxY = geom.GetEnvelope()
    x_siz = img.RasterXSize
    y_siz = img.RasterYSize

    # Step 2: extract one feature from the original, and make a new shapefile.
    new_data_source = shp_drv.CreateDataSource('result.shp')
    new_layer = new_data_source.CreateLayer("feature", geom_type=osgeo.ogr.wkbPolygon, srs=srs)
    new_feat = osgeo.ogr.Feature(layer.GetLayerDefn())
    new_feat.SetGeometry(geom)
    new_layer.CreateFeature(new_feat)

    # Close datasets. GDAL needs this as it implements some of the work in the destructor.
    new_feat = None
    new_data_source = None
    new_layer = None

    # Step 3: Rasterize the new shapefile to an in-memory buffer.
    mem_output = osgeo.gdal.GetDriverByName('MEM').Create('', x_siz, y_siz, 1, osgeo.gdal.GDT_Byte)
    mem_output.SetProjection(img.GetProjection())
    mem_output.SetGeoTransform(img.GetGeoTransform())
    data_source = shp_drv.Open('result.shp', 0)
    new_layer = data_source.GetLayer()
    osgeo.gdal.RasterizeLayer(mem_output, [1], new_layer)

    # Step 4: Copy the active pixels to the output file.
    # The extra copy between steps 3 & 4 is needed to get a Sparse GeoTIFF file, where empty
    # areas of the raster are omitted from the file entirely. This does reduce the size of the
    # file, but the main reason for doing it is to allow the subsequent steps using this raster
    # as a mask to completely skip processing the empty blocks.
    output = osgeo.gdal.GetDriverByName('GTiff').Create(
            outfile, x_siz, y_siz, 1, osgeo.gdal.GDT_Byte,
            # ZSTD: 2.3 Megs, DEFLATE: 3.8 Megs, LZW: 15 Megs, PACKBITS: 67 Megs
            options=['NBITS=1', 'COMPRESS=ZSTD', 'TILED=YES', 'NUM_THREADS=2', 'SPARSE_OK=TRUE'])
    output.SetProjection(img.GetProjectionRef())
    output.SetGeoTransform(img.GetGeoTransform())

    # copy the active pixels.
    x_blksiz = y_blksiz = 256
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
            data = mem_output.GetRasterBand(1).ReadAsArray(x_off, y_off, cols, rows)
            if np.count_nonzero(data) != 0:
                output.GetRasterBand(1).WriteArray(data, x_off, y_off)



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
        status_e = status_p = status_f = status_h = 0
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
                if flags & osgeo.gdal.GDAL_DATA_COVERAGE_STATUS_EMPTY and pct == 0.0:
                    status_h += 1
                elif flags & osgeo.gdal.GDAL_DATA_COVERAGE_STATUS_DATA and pct == 100.0:
                    status_f += 1
                elif flags & (osgeo.gdal.GDAL_DATA_COVERAGE_STATUS_EMPTY |
                        osgeo.gdal.GDAL_DATA_COVERAGE_STATUS_DATA) != 0:
                    status_p += 1
                else:
                    status_e += 1
        print(f"full: {status_f}  hole: {status_h} partial: {status_p} error: {status_e}")

    else:
        filename = 'data/ucl_elie/ESACCI-LC-L4-LCCS-Map-300m-P1Y-2015-v2.0.7.tif'
        print('Opening' + filename)
        img = osgeo.gdal.Open(filename, osgeo.gdal.GA_ReadOnly)
        shapefilename = 'data/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp'
        rasterize_shapefile(img=img, shapefilename=shapefilename, outfile='result.tif')
