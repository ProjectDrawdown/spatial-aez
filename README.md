##Process Köppen-Geiger climate classification maps##

Code in this repository processes the data files from the Nature article
["Present and future Köppen-Geiger climate classification maps at 1-km resolution"]
(https://www.nature.com/articles/sdata2018214.pdf)

[Paper's data files](http://www.gloh2o.org/koppen/) retrieved 8/22/2019.
[Natural Earth topology files](http://www.naturalearthdata.com/downloads/) retrieved 8/22/2019.

The output of this code is a pair of CSV files for present and future, with a
column per Köppen-Geiger class and row per country. Names are normalized to
those used in [Project Drawdown](https://drawdown.org). Square kilometers per
[Köppen-Geiger class](https://en.wikipedia.org/wiki/K%C3%B6ppen_climate_classification)
are calculated per country, correcting for WGS84 projection.
