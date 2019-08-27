**Process Köppen-Geiger climate classification maps**

Code in this repository processes the data files from the Nature article
"Present and future Köppen-Geiger climate classification maps at 1-km resolution"
https://www.nature.com/articles/sdata2018214.pdf

Data files retrieved from http://www.gloh2o.org/koppen/ on 8/22/2019.
Topology files retrieved from http://www.naturalearthdata.com/downloads/ on 8/22/2019.

The output of this code is a pair of CSV files for present and future with a
column per Köppen-Geiger class and row per country, with names normalized to
those used in [Project Drawdown](https://drawdown.org). Square kilometers per
KG class are calculated per country.
