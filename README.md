## Process spatial climate maps

Code in this repository extracts land area data from spatial maps for use in climate solution models.

The output of this code is a series of CSV files for present and future, with
a row per country and column per data class.  Names are normalized to
those used in [Project Drawdown](https://drawdown.org). Square kilometers per
[Köppen-Geiger class](https://en.wikipedia.org/wiki/K%C3%B6ppen_climate_classification)
are calculated per country, correcting for WGS84 projection.

Note that the data processed in this repository comes from external sources, several of which require
attribution in the form of a citation of their contribution. Please see LICENSE.md for details and links.


### Köppen-Geiger
Data files come from the Nature article
["Present and future Köppen-Geiger climate classification maps at 1-km resolution"](https://www.nature.com/articles/sdata2018214.pdf).

[Paper's data files](http://www.gloh2o.org/koppen/) retrieved 22 Aug 2019.


### Land Cover
Data comes from the [European Space Agency Climate Change Initiative](http://maps.elie.ucl.ac.be/CCI/viewer/download.php).

[Land Cover GeoTIFF](https://storage.googleapis.com/cci-lc-v207/ESACCI-LC-L4-LCCS-Map-300m-P1Y-2015-v2.0.7.zip) retrieved 19 Sep 2019.


### Administrative Boundaries
World maps are processed into administrative boundaries using shapefiles provided by [Natural Earth](https://www.naturalearthdata.com).

[Natural Earth topology files](https://www.naturalearthdata.com/downloads/) retrieved 22 Aug 2019.
