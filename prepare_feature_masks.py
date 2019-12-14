import os.path
import tempfile
import time

import numpy as np
import osgeo.gdal
import osgeo.ogr

def rasterize_one_feature(img, feature, layer, outfile):
    """Rasterize a shapefile to TIFF."""
    # Step 1: extract one feature from the original, and make a new shapefile.
    tmpdir = tempfile.TemporaryDirectory()
    new_shapefile = os.path.join(tmpdir.name, 'feature.shp')
    shp_drv = osgeo.ogr.GetDriverByName("ESRI Shapefile")
    new_data_source = shp_drv.CreateDataSource(new_shapefile)
    srs = layer.GetSpatialRef()
    new_layer = new_data_source.CreateLayer("feature", geom_type=osgeo.ogr.wkbPolygon, srs=srs)
    new_feat = osgeo.ogr.Feature(layer.GetLayerDefn())
    new_feat.SetGeometry(feature.GetGeometryRef())
    new_layer.CreateFeature(new_feat)

    # Close datasets. GDAL needs this as it implements some of the work in the destructor.
    new_feat = None
    new_data_source = None
    new_layer = None

    # Step 2: Rasterize the new shapefile to an in-memory buffer.
    x_siz = img.RasterXSize
    y_siz = img.RasterYSize
    mem_output = osgeo.gdal.GetDriverByName('MEM').Create('', x_siz, y_siz, 1, osgeo.gdal.GDT_Byte)
    mem_output.SetProjection(img.GetProjection())
    mem_output.SetGeoTransform(img.GetGeoTransform())
    data_source = shp_drv.Open(new_shapefile, 0)
    new_layer = data_source.GetLayer()
    osgeo.gdal.RasterizeLayer(mem_output, [1], new_layer)

    # Step 3: Copy the active pixels to the output file.
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


def process_shapefile():
    shapefilename = 'data/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp'
    shp_drv = osgeo.ogr.GetDriverByName("ESRI Shapefile")
    shapefile = shp_drv.Open(shapefilename, 0)
    layer = shapefile.GetLayerByIndex(0)

    img = osgeo.gdal.Open('data/Beck_KG_V1/Beck_KG_V1_present_0p0083.tif', osgeo.gdal.GA_ReadOnly)
    for idx, feature in enumerate(layer):
        a3 = feature.GetField("SOV_A3")
        outfile = f'masks/{a3}_{idx}_1km_mask._tif'
        print(f'{outfile}')
        rasterize_one_feature(img=img, feature=feature, layer=layer, outfile=outfile)

    img = osgeo.gdal.Open('data/copernicus/C3S-LC-L4-LCCS-Map-300m-P1Y-2018-v2.1.1.tif', osgeo.gdal.GA_ReadOnly)
    for idx, feature in enumerate(layer):
        a3 = feature.GetField("SOV_A3")
        outfile = f'masks/{a3}_{idx}_333m_mask._tif'
        print(f'{outfile}')
        rasterize_one_feature(img=img, feature=feature, layer=layer, outfile=outfile)

    img = osgeo.gdal.Open('data/Beck_KG_V1/Beck_KG_V1_present_0p5.tif', osgeo.gdal.GA_ReadOnly)
    for idx, feature in enumerate(layer):
        a3 = feature.GetField("SOV_A3")
        outfile = f'masks/{a3}_{idx}_0p5_mask._tif'
        print(f'{outfile}')
        rasterize_one_feature(img=img, feature=feature, layer=layer, outfile=outfile)


if __name__ == '__main__':
    process_shapefile()
