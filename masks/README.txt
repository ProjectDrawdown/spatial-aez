Files in this directory are sparse TIF files created using GDAL.
Sparse in this context means that blocks made up entirely of NoData 
pixels have no storage allocated. GDAL can handle this, but many
TIFF implementations do not. We've given the files an unusual
file extension with an extra underscore to make it really clear
that they won't open in (for example) MacOS Preview.

The files in this directory were created using prepare_feature_masks.py.
