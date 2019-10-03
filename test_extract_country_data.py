import glob
import os.path
import pytest
import tempfile

import osgeo.gdal
import pandas as pd
import extract_country_data as ecd

pd.set_option("display.max_rows", 500)
pd.set_option("display.max_columns", 40)

def test_areas_reasonable():
    num = 0
    for filename in glob.glob('results/*.csv'):
        print(f"{filename}")
        num = num + 1
        df = pd.read_csv(filename).set_index('Country')
        for country, row in df.iterrows():
            if country == 'Antarctica':
                continue
            area = row.sum()
            expected = expected_area[country.upper()]
            print(f"{country}: {area} expected={expected}")
            if expected < 2500 and area < 2500:
                continue
            elif expected < 35000 and area < 35000:
                if 'workability' in filename.lower():
                    # FAO soil workability data omits a number of small countries, and is coarse
                    # enough to over-estimate a number of medium-sized countries. Just skip them,
                    # the errors are not enough to change conclusions.
                    pass
                else:
                    assert area > (expected * 0.6)
                    assert area < (expected * 1.20)
            else:
                if 'workability' in filename.lower() and country == 'Norway':
                    # FAO data is old enough that it does not reflect the resolution of the
                    # boundary dispute between Russia and Norway in 2010 which added substantial
                    # Arctic territory to Norway. Just skip it.
                    continue
                assert area > (expected * 0.85)
                assert area < (expected * 1.07)
        print("\n")
    assert num >= 4


def test_country_land_cover_vs_excel():
    df = pd.read_csv('results/FAO-Land-Cover-by-country.csv').set_index('Country')
    regional = pd.DataFrame(0, index=['OECD90', 'Eastern Europe', 'Asia (Sans Japan)',
        'Middle East and Africa', 'Latin America', 'China', 'India', 'EU', 'USA'],
        columns=df.columns.copy())
    for country, row in df.iterrows():
        region = region_mapping[country]
        if region is not None:
            regional.loc[region, :] += row
    gaez = pd.DataFrame(gaez_land_areas[1:], columns=gaez_land_areas[0]).set_index('Country')
    for country, row in df.iterrows():
        if country not in gaez.index:
            continue

        percent = gaez.loc[country, "Forest Land"] / 100.0
        total = gaez.loc[country, "All Classes"]
        expected = total * percent
        if expected > 50000:
            actual = row['Tree Covered Areas']
            assert actual > expected * 0.6
            assert actual < expected * 2.4

        percent = gaez.loc[country, "Urban Land"] / 100.0
        total = gaez.loc[country, "All Classes"]
        expected = total * percent
        if expected > 50000:
            actual = row['Artificial Surfaces']
            assert actual > expected * 0.05
            assert actual < expected * 2.4

        percent = gaez.loc[country, "Grassland"] / 100.0
        total = gaez.loc[country, "All Classes"]
        expected = total * percent
        if expected > 50000:
            actual = row['Grassland'] + row['Sparse vegetation']
            assert actual > expected * 0.0002
            assert actual < expected * 2.4

        percent = (gaez.loc[country, "Irrigated Cultivated Land"] +
                gaez.loc[country, "Rainfed Cultivated Land"]) / 100.0
        total = gaez.loc[country, "All Classes"]
        expected = total * percent
        if expected > 50000:
            actual = row['Cropland']
            assert actual > expected * 0.25
            assert actual < expected * 3.1

        percent = gaez.loc[country, "Water"] / 100.0
        total = gaez.loc[country, "All Classes"]
        expected = total * percent
        if expected > 50000:
            actual = row['Waterbodies']
            assert actual > expected * 0.5
            assert actual < expected * 2.4

        # Not accounted for:
        # Shrubs Covered Areas,"Herbaceous vegetation, aquatic or regularly flooded",Baresoil,Snow and glaciers
        # expected = gaez.loc[country, "Barren Land"]


def test_regional_land_cover_vs_excel_fao():
    df = pd.read_csv('results/FAO-Land-Cover-by-country.csv').set_index('Country')
    gaez = pd.DataFrame(gaez_land_areas[1:], columns=gaez_land_areas[0]).set_index('Country')
    fao_region = pd.DataFrame(0, index=['OECD90', 'Eastern Europe', 'Asia (Sans Japan)',
        'Middle East and Africa', 'Latin America', 'China', 'India', 'EU', 'USA'],
        columns=df.columns.copy())
    gaez_region = pd.DataFrame(0, index=['OECD90', 'Eastern Europe', 'Asia (Sans Japan)',
        'Middle East and Africa', 'Latin America', 'China', 'India', 'EU', 'USA'],
        columns=gaez.columns.copy())

    for country, row in df.iterrows():
        region = region_mapping[country]
        if region is not None:
            fao_region.loc[region, :] += row
    for country, row in gaez.iterrows():
        region = region_mapping[country]
        if region is not None:
            total = gaez.loc[country, "All Classes"]

            percent = gaez.loc[country, "Forest Land"] / 100.0
            gaez_region.loc[region, "Forest Land"] += (percent * total)

            percent = gaez.loc[country, "Grassland"] / 100.0
            gaez_region.loc[region, "Grassland"] += (percent * total)

            percent = gaez.loc[country, "Irrigated Cultivated Land"] / 100.0
            gaez_region.loc[region, "Irrigated Cultivated Land"] += (percent * total)

            percent = gaez.loc[country, "Rainfed Cultivated Land"] / 100.0
            gaez_region.loc[region, "Rainfed Cultivated Land"] += (percent * total)

    for region in gaez_region.index:
        expected = gaez_region.loc[region, "Forest Land"]
        actual = fao_region.loc[region, "Tree Covered Areas"]
        assert actual > expected * 0.6
        assert actual < expected * 1.5

        expected = gaez_region.loc[region, "Grassland"]
        actual = (fao_region.loc[region, "Grassland"] + fao_region.loc[region, "Sparse vegetation"] +
                fao_region.loc[region, "Baresoil"])
        assert actual > expected * 0.3
        assert actual < expected * 1.7

        expected = (gaez_region.loc[region, "Irrigated Cultivated Land"] +
                gaez_region.loc[region, "Rainfed Cultivated Land"])
        actual = fao_region.loc[region, "Cropland"]
        assert actual > expected * 0.8
        assert actual < expected * 1.9


@pytest.mark.skip(reason="still developing this test's asserts")
def test_world_land_cover_vs_excel_esa():
    df = pd.read_csv('results/Land-Cover-by-country.csv').set_index('Country')
    df.columns = df.columns.astype(int)
    forest = grassland = shrubland = cropland = 0
    for country, row in df.iterrows():
        #forest += row[12] + row[50] + row[60] + row[61] + row[62] + row[70] + row[71] + row[72]
        forest += row[50] + row[60] + row[61] + row[62] + row[70] + row[71] + row[72]
        forest += row[80] + row[81] + row[82] + row[90] + row[160] + row[170]
        shrubland += row[40] + row[100] + row[110] + row[120] + row[121] + row[122] + row[180]
        shrubland += row[12]
        grassland += row[11] + row[130] + row[150] + row[151] + row[152] + row[153]
        cropland += row[10] + row[20] + row[30]

    print(f"forest: {forest} grassland: {grassland} shrubland: {shrubland} cropland: {cropland}")
    assert False


@pytest.mark.skip(reason="still developing this test's asserts")
def test_world_land_cover_vs_excel_fao():
    df = pd.read_csv('results/FAO-Land-Cover-by-country.csv').set_index('Country')
    forest = grassland = shrubland = cropland = 0
    for country, row in df.iterrows():
        #forest += row[12] + row[50] + row[60] + row[61] + row[62] + row[70] + row[71] + row[72]
        forest += row["Tree Covered Areas"]
        shrubland += row["Shrubs Covered Areas"]
        grassland += row["Grassland"] + row["Sparse vegetation"]
        cropland += row["Cropland"]

    print(f"forest: {forest} grassland: {grassland} shrubland: {shrubland} cropland: {cropland}")
    assert False


def test_kg():
    shapefilename = 'data/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp'
    mapfilename = 'data/Beck_KG_V1/Beck_KG_V1_present_0p5.tif'
    img = osgeo.gdal.Open(mapfilename, osgeo.gdal.GA_ReadOnly)
    ctable = img.GetRasterBand(1).GetColorTable()
    lookupobj = ecd.KGlookup(ctable)
    csvfile = tempfile.NamedTemporaryFile()
    assert os.path.getsize(csvfile.name) == 0
    ecd.process_map(shapefilename=shapefilename, mapfilename=mapfilename, lookupobj=lookupobj,
                    csvfilename=csvfile.name)
    assert os.path.getsize(csvfile.name) != 0
    df = pd.read_csv(csvfile.name).set_index('Country').sum(axis=1)
    assert 'United States of America' in df.index
    assert df['United States of America'] > 1

def test_lc():
    shapefilename = 'data/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp'
    mapfilename = 'data/ucl_elie/test_small.tif'
    lookupobj = ecd.ESA_LC_lookup()
    csvfile = tempfile.NamedTemporaryFile()
    assert os.path.getsize(csvfile.name) == 0
    ecd.process_map(shapefilename=shapefilename, mapfilename=mapfilename, lookupobj=lookupobj,
                    csvfilename=csvfile.name)
    assert os.path.getsize(csvfile.name) != 0
    df = pd.read_csv(csvfile.name).set_index('Country').sum(axis=1)
    assert 'United States of America' in df.index
    assert df['United States of America'] > 1

def test_sl():
    shapefilename = 'data/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp'
    mapfilename = 'data/geomorpho90m/test_small.tif'
    lookupobj = ecd.SlopeLookup()
    csvfile = tempfile.NamedTemporaryFile()
    assert os.path.getsize(csvfile.name) == 0
    ecd.process_map(shapefilename=shapefilename, mapfilename=mapfilename, lookupobj=lookupobj,
                    csvfilename=csvfile.name)
    assert os.path.getsize(csvfile.name) != 0
    df = pd.read_csv(csvfile.name).set_index('Country').sum(axis=1)
    assert 'United States of America' in df.index
    assert df['United States of America'] > 1

def test_wk():
    shapefilename = 'data/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp'
    mapfilename = 'data/FAO/workability_FAO_sq7_10km.tif'
    lookupobj = ecd.WorkabilityLookup()
    csvfile = tempfile.NamedTemporaryFile()
    assert os.path.getsize(csvfile.name) == 0
    ecd.process_map(shapefilename=shapefilename, mapfilename=mapfilename, lookupobj=lookupobj,
                    csvfilename=csvfile.name)
    assert os.path.getsize(csvfile.name) != 0
    df = pd.read_csv(csvfile.name).set_index('Country').sum(axis=1)
    assert 'United States of America' in df.index
    assert df['United States of America'] > 1


# From https://www.cia.gov/library/publications/the-world-factbook/rankorder/2147rank.html
expected_area = {
    "AFGHANISTAN": 652230,
    "AKROTIRI": 123,
    "ALBANIA": 28748,
    "ALGERIA": 2381741,
    "AMERICAN SAMOA": 199,
    "ANDORRA": 468,
    "ANGOLA": 1246700,
    "ANGUILLA": 91,
    "ANTARCTICA": 14000000,
    "ANTIGUA AND BARBUDA": 443,
    "ARGENTINA": 2780400,
    "ARMENIA": 29743,
    "ARUBA": 180,
    "ASHMORE AND CARTIER ISLANDS": 5,
    "AUSTRALIA": 7741220,
    "AUSTRIA": 83871,
    "AZERBAIJAN": 86600,
    "BAHAMAS": 13880,
    "BAHRAIN": 760,
    "BANGLADESH": 148460,
    "BARBADOS": 430,
    "BELARUS": 207600,
    "BELGIUM": 30528,
    "BELIZE": 22966,
    "BENIN": 112622,
    "BERMUDA": 54,
    "BHUTAN": 38394,
    "BOLIVIA": 1098581,
    "BOSNIA AND HERZEGOVINA": 51197,
    "BOTSWANA": 581730,
    "BOUVET ISLAND": 49,
    "BRAZIL": 8515770,
    "BRITISH INDIAN OCEAN TERRITORY": 60,
    "BRITISH VIRGIN ISLANDS": 151,
    "BRUNEI": 5765,
    "BULGARIA": 110879,
    "BURKINA FASO": 274200,
    "MYANMAR": 676578,
    "BURUNDI": 27830,
    "CAPE VERDE": 4033,
    "CAMBODIA": 181035,
    "CAMEROON": 475440,
    "CANADA": 9984670,
    "CAYMAN ISLANDS": 264,
    "CENTRAL AFRICAN REPUBLIC": 622984,
    "CHAD": 1284000,
    "CHILE": 756102,
    "CHINA": 9596960,
    "CHRISTMAS ISLAND": 135,
    "CLIPPERTON ISLAND": 6,
    "COCOS (KEELING) ISLANDS": 14,
    "COLOMBIA": 1138910,
    "COMOROS": 2235,
    "DEMOCRATIC REPUBLIC OF THE CONGO": 2344858,
    "CONGO": 342000,
    "COOK ISLANDS": 236,
    "CORAL SEA ISLANDS": 3,
    "COSTA RICA": 51100,
    "CÔTE D'IVOIRE": 322463,
    "CROATIA": 56594,
    "CUBA": 110860,
    "CURAÇAO": 444,
    "CYPRUS": 9251,
    "CZECH REPUBLIC": 78867,
    "DENMARK": 43094,
    "DHEKELIA": 131,
    "DJIBOUTI": 23200,
    "DOMINICA": 751,
    "DOMINICAN REPUBLIC": 48670,
    "ECUADOR": 283561,
    "EGYPT": 1001450,
    "EL SALVADOR": 21041,
    "EQUATORIAL GUINEA": 28051,
    "ERITREA": 117600,
    "ESTONIA": 45228,
    "ETHIOPIA": 1104300,
    "FALKLAND ISLANDS (ISLAS MALVINAS)": 12173,
    "FAROE ISLANDS": 1393,
    "FIJI": 18274,
    "FINLAND": 338145,
    "FRANCE": 643801,
    "FRENCH POLYNESIA": 4167,
    "FRENCH SOUTHERN AND ANTARCTIC LANDS": 55,
    "GABON": 267667,
    "GAMBIA": 11300,
    "GAZA STRIP": 360,
    "GEORGIA": 69700,
    "GERMANY": 357022,
    "GHANA": 238533,
    "GIBRALTAR": 7,
    "GREECE": 131957,
    "GREENLAND": 2166086,
    "GRENADA": 344,
    "GUAM": 544,
    "GUATEMALA": 108889,
    "GUERNSEY": 78,
    "GUINEA": 245857,
    "GUINEA-BISSAU": 28120,  # 36125, https://en.wikipedia.org/wiki/Geography_of_Guinea-Bissau land area
    "GUYANA": 214969,
    "HAITI": 27750,
    "HEARD ISLAND AND MCDONALD ISLANDS": 412,
    "HOLY SEE": 0,
    "HONDURAS": 112090,
    "HONG KONG": 1108,
    "HUNGARY": 93028,
    "ICELAND": 103000,
    "INDIA": 3287263,
    "INDONESIA": 1904569,
    "IRAN": 1648195,
    "IRAQ": 438317,
    "IRELAND": 70273,
    "ISLE OF MAN": 572,
    "ISRAEL": 20770,
    "ITALY": 301340,
    "JAMAICA": 10991,
    "JAN MAYEN": 377,
    "JAPAN": 377915,
    "JERSEY": 116,
    "JORDAN": 89342,
    "KAZAKHSTAN": 2724900,
    "KENYA": 580367,
    "KIRIBATI": 811,
    "DEMOCRATIC PEOPLE'S REPUBLIC OF KOREA": 120538,
    "REPUBLIC OF KOREA (SOUTH KOREA)": 99720,
    "KOSOVO": 10887,
    "KUWAIT": 17818,
    "KYRGYZSTAN": 199951,
    "LAO PEOPLE'S DEMOCRATIC REPUBLIC": 236800,
    "LATVIA": 64589,
    "LEBANON": 10400,
    "LESOTHO": 30355,
    "LIBERIA": 96320,  # 111369,  https://www.land-links.org/country-profile/liberia/
    "LIBYA": 1759540,
    "LIECHTENSTEIN": 160,
    "LITHUANIA": 65300,
    "LUXEMBOURG": 2586,
    "MACAU": 28,
    "THE FORMER YUGOSLAV REPUBLIC OF MACEDONIA": 25713,
    "MADAGASCAR": 587041,
    "MALAWI": 118484,
    "MALAYSIA": 329847,
    "MALDIVES": 298,
    "MALI": 1240192,
    "MALTA": 316,
    "MARSHALL ISLANDS": 181,
    "MAURITANIA": 1030700,
    "MAURITIUS": 2040,
    "MEXICO": 1964375,
    "MICRONESIA (FEDERATED STATES OF)": 702,
    "MOLDOVA": 33851,
    "MONACO": 2,
    "MONGOLIA": 1564116,
    "MONTENEGRO": 13812,
    "MONTSERRAT": 102,
    "MOROCCO": 590000,  # 446550,  disputed territory w/ Western Sahara
    "MOZAMBIQUE": 799380,
    "NAMIBIA": 824292,
    "NAURU": 21,
    "NAVASSA ISLAND": 5,
    "NEPAL": 147181,
    "NETHERLANDS": 41543,
    "NEW CALEDONIA": 18575,
    "NEW ZEALAND": 268838,
    "NICARAGUA": 130370,
    "NIGER": 1267000,
    "NIGERIA": 923768,
    "NIUE": 260,
    "NORFOLK ISLAND": 36,
    "NORTHERN MARIANA ISLANDS": 464,
    "NORWAY": 385203,   # 323802,  resolved Artic dispute added territory
    "OMAN": 309500,
    "PAKISTAN": 881913,  # 796095, https://en.wikipedia.org/wiki/Pakistan
    "PALAU": 459,
    "PALESTINE": 6220,
    "PANAMA": 75420,
    "PAPUA NEW GUINEA": 462840,
    "PARACEL ISLANDS": 8,
    "PARAGUAY": 406752,
    "PERU": 1285216,
    "PHILIPPINES": 300000,
    "PITCAIRN ISLANDS": 47,
    "POLAND": 312685,
    "PORTUGAL": 92090,
    "PUERTO RICO": 9104,
    "QATAR": 11586,
    "ROMANIA": 238391,
    "RUSSIAN FEDERATION": 17098242,
    "RWANDA": 26338,
    "SAINT BARTHELEMY": 25,
    "SAINT HELENA ASCENSION AND TRISTAN DA CUNHA": 394,
    "SAINT KITTS AND NEVIS": 261,
    "SAINT LUCIA": 616,
    "SAINT MARTIN": 54,
    "SAINT PIERRE AND MIQUELON": 242,
    "SAINT VINCENT AND THE GRENADINES": 389,
    "SAMOA": 2831,
    "SAN MARINO": 61,
    "SÃO TOMÉ AND PRINCIPE": 964,
    "SAUDI ARABIA": 2149690,
    "SENEGAL": 196722,
    "SERBIA": 77474,
    "SEYCHELLES": 455,
    "SIERRA LEONE": 71740,
    "SINGAPORE": 697,
    "SINT MAARTEN": 34,
    "SLOVAKIA": 49035,
    "SLOVENIA": 20273,
    "SOLOMON ISLANDS": 28896,
    "SOMALIA": 637657,
    "SOUTH AFRICA": 1219090,
    "SOUTH GEORGIA AND SOUTH SANDWICH ISLANDS": 3903,
    "SOUTH SUDAN": 644329,
    "SPAIN": 505370,
    "SPRATLY ISLANDS": 5,
    "SRI LANKA": 65610,
    "SUDAN": 1861484,
    "SURINAME": 163820,
    "SVALBARD": 62045,
    "SWAZILAND": 17364,
    "SWEDEN": 450295,
    "SWITZERLAND": 41277,
    "SYRIAN ARAB REPUBLIC": 185180,
    "TAIWAN": 35980,
    "TAJIKISTAN": 144100,
    "UNITED REPUBLIC OF TANZANIA": 947300,
    "THAILAND": 513120,
    "TIMOR-LESTE": 14874,
    "TOGO": 56785,
    "TOKELAU": 12,
    "TONGA": 747,
    "TRINIDAD AND TOBAGO": 5128,
    "TUNISIA": 163610,
    "TURKEY": 783562,
    "TURKMENISTAN": 488100,
    "TURKS AND CAICOS ISLANDS": 948,
    "TUVALU": 26,
    "UGANDA": 241038,
    "UKRAINE": 603550,
    "UNITED ARAB EMIRATES": 77700,  # 83600, disputed islands in Strait of Hormuz
    "UNITED KINGDOM": 243610,
    "UNITED STATES PACIFIC ISLAND WILDLIFE REFUGES": 22,
    "UNITED STATES OF AMERICA": 9833517,
    "URUGUAY": 176215,
    "UZBEKISTAN": 447400,
    "VANUATU": 12189,
    "VENEZUELA": 912050,
    "VIETNAM": 331210,
    "VIRGIN ISLANDS": 1910,
    "WAKE ISLAND": 7,
    "WALLIS AND FUTUNA": 142,
    "WEST BANK": 5860,
    "WESTERN SAHARA": 90000,  # 266000, disputed territory w/ Morocco
    "YEMEN": 527968,
    "ZAMBIA": 752618,
    "ZIMBABWE": 390757,
    }


# Taken from Regions-Countries sorting tab of Excel model
region_mapping = {
    "Afghanistan": ["Asia (Sans Japan)"],
    "Akrotiri": None,
    "Aland": None,
    "Aland Islands": None,
    "Åland Islands": None,
    "Albania": ["Eastern Europe"],
    "Algeria": ["Middle East and Africa"],
    "American Samoa": ["Asia (Sans Japan)", "USA"],
    "Andorra": ["OECD90"],
    "Angola": ["Middle East and Africa"],
    "Anguilla": ["Latin America"],
    "Antarctica": None,
    "Antigua and Barbuda": ["Latin America"],
    "Antilles (Netherlands)": ["Latin America"],
    "Argentina": ["Latin America"],
    "Armenia": ["Eastern Europe"],
    "Aruba": ["Latin America"],
    "Australia": ["OECD90"],
    "Austria": ["OECD90", "EU"],
    "Azerbaijan": ["Eastern Europe"],
    "Bahamas": ["Latin America"],
    "The Bahamas": ["Latin America"],
    "Bahrain": ["Middle East and Africa"],
    "Baikonur": ["Eastern Europe"],
    "Bangladesh": ["Asia (Sans Japan)"],
    "Barbados": ["Latin America"],
    "Belarus": ["Eastern Europe"],
    "Belgium": ["OECD90", "EU"],
    "Belize": ["Latin America"],
    "Benin": ["Middle East and Africa"],
    "Bermuda": ["Latin America"],
    "Bhutan": ["Asia (Sans Japan)"],
    "Bolivia (Plurinational State of)": ["Latin America"],
    "Bolivia": ["Latin America"],
    "Bolivia, Plurinational State of": ["Latin America"],
    "Bosnia and Herzegovina": ["Eastern Europe"],
    "Bosnia and Herz.": ["Eastern Europe"],
    "Botswana": ["Middle East and Africa"],
    "Brazil": ["Latin America"],
    "British Indian Ocean Territory": None,
    "British Virgin Islands": ["Latin America"],
    "Virgin Islands, British": ["Latin America"],
    "Brunei Darussalam": ["Asia (Sans Japan)"],
    "Brunei": ["Asia (Sans Japan)"],
    "Bulgaria": ["Eastern Europe", "EU"],
    "Burkina Faso": ["Middle East and Africa"],
    "Burundi": ["Middle East and Africa"],
    "Cambodia": ["Asia (Sans Japan)"],
    "Cameroon": ["Middle East and Africa"],
    "Canada": ["OECD90"],
    "Cape Verde": ["Middle East and Africa"],
    "Cayman Islands": ["Latin America"],
    "Central African Republic": ["Middle East and Africa"],
    "Central African Rep.": ["Middle East and Africa"],
    "Chad": ["Middle East and Africa"],
    "Channel Islands": ["OECD90"],
    "Chile": ["Latin America"],
    "China": ["Asia (Sans Japan)", "China"],
    "Christmas Island": None,
    "Cocos Islands": None,
    "Colombia": ["Latin America"],
    "Comoros": ["Middle East and Africa"],
    "Congo": ["Middle East and Africa"],
    "Congo, the Democratic Republic of the": ["Middle East and Africa"],
    "Republic of the Congo": ["Middle East and Africa"],
    "Cook Islands": None,
    "Costa Rica": ["Latin America"],
    "Côte d'Ivoire": ["Middle East and Africa"],
    "Croatia": ["Eastern Europe", "EU"],
    "Cuba": ["Latin America"],
    "Curaçao": ["Latin America"],
    "Cyprus": ["Eastern Europe", "EU"],
    "Cyprus U.N. Buffer Zone": ["Eastern Europe"],
    "Northern Cyprus": ["Eastern Europe"],
    "Czech Republic": ["Eastern Europe", "EU"],
    "Czech Rep.": ["Eastern Europe", "EU"],
    "Democratic People's Republic of Korea": ["Asia (Sans Japan)"],
    "Dem. Rep. Korea": ["Asia (Sans Japan)"],
    "Korea, Democratic People's Republic of": ["Asia (Sans Japan)"],
    "North Korea": ["Asia (Sans Japan)"],
    "Democratic Republic of the Congo": ["Middle East and Africa"],
    "Dem. Rep. Congo": ["Middle East and Africa"],
    "Denmark": ["OECD90", "EU"],
    "Dhekelia": ["Eastern Europe"],
    "Djibouti": ["Middle East and Africa"],
    "Dominica": None,
    "Dominican Republic": ["Latin America"],
    "Dominican Rep.": ["Latin America"],
    "East Timor": ["Asia (Sans Japan)"],
    "Timor-Leste": ["Asia (Sans Japan)"],
    "Ecuador": ["Latin America"],
    "Egypt": ["Middle East and Africa"],
    "El Salvador": ["Latin America"],
    "Equatorial Guinea": ["Middle East and Africa"],
    "Eq. Guinea": ["Middle East and Africa"],
    "Eritrea": ["Middle East and Africa"],
    "Estonia": ["Eastern Europe", "EU"],
    "Ethiopia": ["Middle East and Africa"],
    "Falkland Islands (Malvinas)": ["Latin America"],
    "Falkland Is.": ["Latin America"],
    "Falkland Islands": ["Latin America"],
    "Faroe Islands": ["OECD90"],
    "Faeroe Is.": ["OECD90"],
    "Fiji": ["OECD90"],
    "Finland": ["OECD90", "EU"],
    "Fr. S. Antarctic Lands": None,
    "French Southern Territories": None,
    "French Southern and Antarctic Lands": None,
    "France": ["OECD90", "EU"],
    "French Guiana": ["Latin America"],
    "French Polynesia": ["OECD90"],
    "Fr. Polynesia": ["OECD90"],
    "Gabon": ["Middle East and Africa"],
    "Gambia": ["Middle East and Africa"],
    "Georgia": ["Eastern Europe"],
    "Germany": ["OECD90", "EU"],
    "Ghana": ["Middle East and Africa"],
    "Gibraltar": ["OECD90"],
    "Greece": ["OECD90", "EU"],
    "Greenland": ["OECD90"],
    "Grenada": None,
    "Guadeloupe": ["Latin America"],
    "Guam": ["OECD90", "USA"],
    "Guatemala": ["Latin America"],
    "Guernsey": ["OECD90"],
    "Guinea": ["Middle East and Africa"],
    "Guinea-Bissau": ["Middle East and Africa"],
    "Guinea Bissau": ["Middle East and Africa"],
    "Guyana": ["Latin America"],
    "Haiti": ["Latin America"],
    "Heard I. and McDonald Is.": None,
    "Heard Island and McDonald Islands": None,
    "Holy See": None,
    "Honduras": ["Latin America"],
    "Hong Kong": ["Asia (Sans Japan)"],
    "Hungary": ["Eastern Europe", "EU"],
    "Iceland": ["OECD90"],
    "India": ["Asia (Sans Japan)", "India"],
    "Indonesia": ["Asia (Sans Japan)"],
    "Iran (Islamic Republic of)": ["Middle East and Africa"],
    "Iran": ["Middle East and Africa"],
    "Iran, Islamic Republic of": ["Middle East and Africa"],
    "Iraq": ["Middle East and Africa"],
    "Ireland": ["OECD90", "EU"],
    "Isle of Man": ["OECD90"],
    "Israel": ["Middle East and Africa"],
    "Italy": ["OECD90", "EU"],
    "Ivory Coast": ["Middle East and Africa"],
    "Jamaica": ["Latin America"],
    "Japan": ["OECD90"],
    "Jersey": None,
    "Jordan": ["Middle East and Africa"],
    "Kazakhstan": ["Eastern Europe"],
    "Kenya": ["Middle East and Africa"],
    "Kiribati": None,
    "Korea": ["Asia (Sans Japan)"],
    "Republic of Korea (South Korea)": ["Asia (Sans Japan)"],
    "Republic of Korea": ["Asia (Sans Japan)"],
    "Korea, Republic of": ["Asia (Sans Japan)"],
    "South Korea": ["Asia (Sans Japan)"],
    "Kosovo": ["Eastern Europe"],
    "Kuwait": ["Middle East and Africa"],
    "Kyrgyzstan": ["Eastern Europe"],
    "Lao People's Democratic Republic": ["Asia (Sans Japan)"],
    "Lao PDR": ["Asia (Sans Japan)"],
    "Laos": ["Asia (Sans Japan)"],
    "Latvia": ["Eastern Europe", "EU"],
    "Lebanon": ["Middle East and Africa"],
    "Lesotho": ["Middle East and Africa"],
    "Liberia": ["Middle East and Africa"],
    "Libya": ["Middle East and Africa"],
    "Liechtenstein": None,
    "Lithuania": ["Eastern Europe", "EU"],
    "Luxembourg": ["OECD90", "EU"],
    "Macao": ["Asia (Sans Japan)"],
    "The former Yugoslav Republic of Macedonia": ["Eastern Europe"],
    "Macedonia": ["Eastern Europe"],
    "Macedonia, the former Yugoslav Republic of": ["Eastern Europe"],
    "Madagascar": ["Middle East and Africa"],
    "Malawi": ["Middle East and Africa"],
    "Malaysia": ["Asia (Sans Japan)"],
    "Maldives": ["Asia (Sans Japan)"],
    "Mali": ["Middle East and Africa"],
    "Malta": ["Eastern Europe", "EU"],
    "Marshall Islands": None,
    "Martinique": ["Latin America"],
    "Mauritania": ["Middle East and Africa"],
    "Mauritius": ["Middle East and Africa"],
    "Mayotte": ["Middle East and Africa"],
    "Mexico": ["Latin America"],
    "Micronesia (Federated States of)": None,
    "Micronesia": None,
    "Micronesia, Federated States of": None,
    "Republic of Moldova": ["Eastern Europe"],
    "Moldova": ["Eastern Europe"],
    "Moldova, Republic of": ["Eastern Europe"],
    "Mongolia": ["Asia (Sans Japan)"],
    "Monaco": None,
    "Montenegro": ["Eastern Europe"],
    "Montserrat": ["Latin America"],
    "Morocco": ["Middle East and Africa"],
    "Mozambique": ["Middle East and Africa"],
    "Myanmar": ["Asia (Sans Japan)"],
    "Namibia": ["Middle East and Africa"],
    "Nauru": None,
    "Nepal": ["Asia (Sans Japan)"],
    "Netherlands": ["OECD90", "EU"],
    "Netherlands Antilles / Curacao": ["Latin America"],
    "New Caledonia": ["OECD90"],
    "New Zealand": ["OECD90"],
    "Nicaragua": ["Latin America"],
    "Niger": ["Middle East and Africa"],
    "Nigeria": ["Middle East and Africa"],
    "Niue": None,
    "Norfolk Island": ["Asia (Sans Japan)"],
    "N. Cyprus": ["Eastern Europe"],
    "Northern Mariana Islands": ["Asia (Sans Japan)", "USA"],
    "Norway": ["OECD90"],
    "Oman": ["Middle East and Africa"],
    "Pakistan": ["Asia (Sans Japan)"],
    "Palau": None,
    "Palestine": ["Middle East and Africa"],
    "Palestine, State of": ["Middle East and Africa"],
    "Panama": ["Latin America"],
    "Papua New Guinea": ["Asia (Sans Japan)"],
    "Paraguay": ["Latin America"],
    "Peru": ["Latin America"],
    "Philippines": ["Asia (Sans Japan)"],
    "Pitcairn Islands": ["Asia (Sans Japan)"],
    "Pitcairn": ["Asia (Sans Japan)"],
    "Poland": ["Eastern Europe", "EU"],
    "Portugal": ["OECD90", "EU"],
    "Puerto Rico": ["Latin America", "USA"],
    "Qatar": ["Middle East and Africa"],
    "Reunion": ["Middle East and Africa"],
    "Romania": ["Eastern Europe", "EU"],
    "Russian Federation": ["Eastern Europe"],
    "Russia": ["Eastern Europe"],
    "Rwanda": ["Middle East and Africa"],
    "Saint Helena, Ascension and Tristan da Cunha": ["Middle East and Africa"],
    "Saint Kitts and Nevis": None,
    "Saint Lucia": None,
    "Saint Pierre and Miquelon": ["OECD90"],
    "Saint Vincent and the Grenadines": None,
    "St. Vin. and Gren.": None,
    "Samoa": ["OECD90"],
    "San Marino": None,
    "Sao Tome and Principe": None,
    "São Tomé and Principe": None,
    "Saudi Arabia": ["Middle East and Africa"],
    "Senegal": ["Middle East and Africa"],
    "Serbia": ["Eastern Europe"],
    "Republic of Serbia": ["Eastern Europe"],
    "Seychelles": None,
    "Siachen Glacier": None,
    "Sierra Leone": ["Middle East and Africa"],
    "Singapore": ["Asia (Sans Japan)"],
    "Slovakia": ["Eastern Europe", "EU"],
    "Slovenia": ["Eastern Europe", "EU"],
    "Solomon Islands": ["OECD90"],
    "Solomon Is.": ["OECD90"],
    "Somalia": ["Middle East and Africa"],
    "Somaliland": ["Middle East and Africa"],
    "South Africa": ["Middle East and Africa"],
    "S. Geo. and S. Sandw. Is.": None,
    "South Georgia and the South Sandwich Islands": None,
    "South Sudan": ["Middle East and Africa"],
    "S. Sudan": ["Middle East and Africa"],
    "Spain": ["OECD90", "EU"],
    "Sri Lanka": ["Asia (Sans Japan)"],
    "St-Martin": ["Latin America"],
    "Saint Martin (French part)": ["Latin America"],
    "Sint Maarten": ["Latin America"],
    "Sint Maarten (Dutch part)": ["Latin America"],
    "Saint Barthélemy": ["Latin America"],
    "Sudan": ["Middle East and Africa"],
    "Suriname": ["Latin America"],
    "Swaziland": ["Middle East and Africa"],
    "Sweden": ["OECD90", "EU"],
    "Switzerland": ["OECD90"],
    "Syrian Arab Republic": ["Middle East and Africa"],
    "Syria": ["Middle East and Africa"],
    "Tahiti": None,
    "Taiwan": ["Asia (Sans Japan)"],
    "Taiwan, Province of China": ["Asia (Sans Japan)"],
    "Tajikistan": ["Eastern Europe"],
    "United Republic of Tanzania": ["Middle East and Africa"],
    "Tanzania": ["Middle East and Africa"],
    "Tanzania, United Republic of": ["Middle East and Africa"],
    "Thailand": ["Asia (Sans Japan)"],
    "Togo": ["Middle East and Africa"],
    "Tokelau": None,
    "Tonga": None,
    "Trinidad and Tobago": ["Latin America"],
    "Tunisia": ["Middle East and Africa"],
    "Turkey": ["OECD90"],
    "Turkmenistan": ["Eastern Europe"],
    "Turks and Caicos Islands": ["Latin America"],
    "Tuvalu": None,
    "Uganda": ["Middle East and Africa"],
    "Ukraine": ["Eastern Europe"],
    "United Arab Emirates": ["Middle East and Africa"],
    "United Kingdom": ["OECD90", "EU"],
    "United States of America": ["OECD90", "USA"],
    "United States": ["OECD90", "USA"],
    "United States Virgin Islands": ["Latin America", "USA"],
    "Virgin Islands, U.S.": ["Latin America", "USA"],
    "Uruguay": ["Latin America"],
    "USNB Guantanamo Bay": None,
    "Uzbekistan": ["Eastern Europe"],
    "Vanuatu": ["OECD90"],
    "Vatican": None,
    "Venezuela (Bolivarian Republic of)": ["Latin America"],
    "Venezuela": ["Latin America"],
    "Venezuela, Bolivarian Republic of": ["Latin America"],
    "Viet Nam": ["Asia (Sans Japan)"],
    "Vietnam": ["Asia (Sans Japan)"],
    "Wallis and Futuna Islands": ["Asia (Sans Japan)"],
    "Wallis and Futuna": ["Asia (Sans Japan)"],
    "West Bank": ["Middle East and Africa"],
    "Western Sahara": ["Middle East and Africa"],
    "W. Sahara": ["Middle East and Africa"],
    "Yemen": ["Middle East and Africa"],
    "Yugoslavia": ["Eastern Europe"],
    "Zambia": ["Middle East and Africa"],
    "Zimbabwe": ["Middle East and Africa"],
}

gaez_land_areas = [
    ["Country", "GAEZ SubRegion", "Drawdown Region", "All Classes", "Irrigated Cultivated Land", "Rainfed Cultivated Land", "Forest Land", "Grassland", "Urban Land", "Barren Land", "Water"],
    ["Afghanistan", "Southern Asia", "Asia (Sans Japan)", 641721, 5.01, 7.58, 1.57, 34.87, 1.02, 49.93, 0.04 ],
    ["Albania", "Southern Europe", "Eastern Europe", 28429, 11.24, 18.92, 26.79, 37.66, 2.46, 0, 1.63 ],
    ["Algeria", "Northern Africa", "Middle East and Africa", 2321707, 0.24, 1.43, 0.91, 6.04, 0.36, 90.84, 0.11 ],
    ["Andorra", "Southern Europe", "OECD90", 475, 0.40, 1.33, 49.02, 46.41, 2.84, 0, 3.30 ],
    ["Angola", "Central Africa", "Middle East and Africa", 1254626, 0.05, 2.82, 46.94, 46.77, 0.46, 2.43, 0.05 ],
    ["Antigua and Barbuda", "Caribbean", "Latin America", 448, 0.17, 3.51, 25.39, 15.86, 1.97, 0, 15.37 ],
    ["Argentina", "South America", "Latin America", 2780530, 0.64, 9.72, 12.46, 63.33, 0.40, 11.60, 1.59 ],
    ["Armenia", "Central Asia", "Eastern Europe", 29596, 9.66, 8.65, 8.15, 67.51, 2.04, 0.23, 3.76 ],
    ["Australia", "Australia and New Zealand", "OECD90", 7709156, 0.26, 5.92, 11.59, 64.68, 0.15, 16.46, 0.28 ],
    ["Austria", "Western Europe", "OECD90", 83618, 1.18, 16.20, 46.63, 32.28, 2.75, 0.67, 0.30 ],
    ["Azerbaijan", "Central Asia", "Eastern Europe", 164692, 8.76, 4.36, 6.06, 29.83, 1.28, 1.44, 0.53 ],
    ["Bahamas", "Caribbean", "Latin America", 13376, 2.72, 1.51, 19.85, 24.16, 0.66, 7.06, 15.16 ],
    ["Bahrain", "Western Asia", "Middle East and Africa", 676, 1.87, 14.80, 0.00, 0.63, 20.23, 30.03, 13.29 ],
    ["Bangladesh", "Southern Asia", "Asia (Sans Japan)", 139322, 26.51, 33.87, 6.87, 6.37, 16.49, 1.53, 5.30 ],
    ["Barbados", "Caribbean", "Latin America", 444, 1.06, 14.80, 1.08, 17.18, 10.41, 0, 23.47 ],
    ["Belarus", "Eastern Europe", "Eastern Europe", 206293, 0.55, 29.72, 38.04, 29.92, 1.51, 0, 0.26 ],
    ["Belgium", "Western Europe", "OECD90", 30511, 1.32, 25.44, 22.10, 37.58, 12.81, 0.02, 0.02 ],
    ["Belize", "Central America", "Latin America", 22366, 0.20, 4.43, 59.37, 27.99, 0.33, 1.40, 2.59 ],
    ["Benin", "Gulf of Guinea", "Middle East and Africa", 116281, 0.11, 28.56, 23.05, 46.01, 1.72, 0, 0.39 ],
    ["Bhutan", "Southern Asia", "Asia (Sans Japan)", 37761, 0.94, 3.64, 77.98, 11.31, 1.67, 4.24, 0.21 ],
    ["Bolivia", "South America", "Latin America", 1089820, 0.12, 3.08, 50.45, 34.42, 0.29, 10.48, 1.16 ],
    ["Bosnia and Herzegovina", "Southern Europe", "Eastern Europe", 50998, 0.10, 21.54, 42.62, 33.59, 2.04, 0, 0.09 ],
    ["Botswana", "Southern Africa", "Middle East and Africa", 580280, 0.01, 0.77, 5.99, 86.77, 0.18, 6.27, 0.01 ],
    ["Brazil", "South America", "Latin America", 8532744, 0.36, 7.37, 57.71, 31.81, 0.59, 0.54, 1.44 ],
    ["Brunei", "South-eastern Asia", "Asia (Sans Japan)", 5902, 0.15, 3.45, 51.31, 35.90, 2.08, 0, 0.86 ],
    ["Bulgaria", "Eastern Europe", "Eastern Europe", 111018, 5.01, 29.38, 30.40, 32.25, 2.43, 0.00, 0.27 ],
    ["Burkina Faso", "Sudano-Sahelian Africa", "Middle East and Africa", 274973, 0.09, 18.23, 7.90, 71.58, 1.65, 0.40, 0.15 ],
    ["Burundi", "Eastern Africa", "Middle East and Africa", 27128, 0.77, 45.05, 8.01, 32.80, 5.53, 0, 7.85 ],
    ["Cambodia", "South-eastern Asia", "Asia (Sans Japan)", 182498, 1.72, 19.19, 50.95, 23.91, 2.07, 0.00, 1.79 ],
    ["Cameroon", "Gulf of Guinea", "Middle East and Africa", 469273, 0.05, 15.15, 51.06, 31.68, 1.10, 0.02, 0.61 ],
    ["Canada", "Northern America", "OECD90", 9806200, 0.08, 5.20, 31.47, 34.22, 0.13, 17.22, 9.22 ],
    ["Cape Verde", "Sudano-Sahelian Africa", "Middle East and Africa", 4076, 2.72, 14.80, 26.74, 31.46, 3.17, 0, 3.30 ],
    ["Central African Republic", "Central Africa", "Middle East and Africa", 624200, 0.00, 3.26, 38.48, 57.90, 0.33, 0, 0.04 ],
    ["Chad", "Sudano-Sahelian Africa", "Middle East and Africa", 1276646, 0.02, 6.55, 1.95, 34.22, 0.30, 56.77, 0.19 ],
    ["Chile", "South America", "Latin America", 753687, 2.51, 0.80, 19.99, 26.85, 0.53, 41.09, 4.23 ],
    ["China", "Eastern Asia", "Asia (Sans Japan)", 9378816, 5.75, 9.21, 18.33, 35.25, 2.81, 27.74, 0.65 ],
    ["Colombia", "South America", "Latin America", 1145383, 0.79, 6.05, 57.21, 34.00, 0.69, 0.28, 0.43 ],
    ["Comoros", "Eastern Africa", "Middle East and Africa", 1685, 0.03, 9.75, 29.87, 6.99, 2.11, 0.93, 9.71 ],
    ["Congo", "Central Africa", "Middle East and Africa", 343881, 0.01, 1.84, 68.30, 28.57, 0.40, 0, 0.76 ],
    ["Cook Islands", "Pacific Islands", None, 249, 2.72, 14.80, 26.74, 31.46, 3.17, 0, 3.30 ],
    ["Costa Rica", "Central America", "Latin America", 51539, 1.93, 11.23, 45.12, 35.09, 1.59, 0.10, 2.75 ],
    ["Croatia", "Southern Europe", "Eastern Europe", 56382, 0.11, 27.53, 37.08, 27.03, 2.09, 0.00, 2.24 ],
    ["Cuba", "Caribbean", "Latin America", 111826, 7.50, 25.98, 20.71, 32.57, 2.46, 0.73, 3.78 ],
    ["Cyprus", "Western Asia", "Eastern Europe", 9010, 4.28, 10.72, 17.64, 51.56, 1.99, 3.82, 3.71 ],
    ["Czech Republic", "Eastern Europe", "Eastern Europe", 78461, 0.65, 41.84, 33.59, 19.78, 4.10, 0, 0.04 ],
    ["Côte d'Ivoire", "Sudano-Sahelian Africa", "Middle East and Africa", 323940, 0.22, 27.48, 31.81, 37.61, 1.57, 0, 0.98 ],
    ["Democratic People's Republic of Korea", "Eastern Asia", "Asia (Sans Japan)", 122305, 10.81, 9.95, 55.89, 17.87, 2.57, 0.01, 0.87 ],
    ["Democratic Republic of the Congo", "Central Africa", "Middle East and Africa", 2343542, 0.00, 6.72, 64.06, 26.55, 0.83, 0.00, 1.83 ],
    ["Denmark", "Northern Europe", "OECD90", 44125, 10.31, 39.91, 10.19, 22.30, 5.02, 0, 4.69 ],
    ["Djibouti", "Eastern Africa", "Middle East and Africa", 21818, 0.04, 14.80, 0.09, 13.28, 0.66, 82.06, 2.26 ],
    ["Dominica", "Caribbean", None, 771, 2.72, 1.09, 25.23, 12.49, 1.03, 14.81, 13.10 ],
    ["Dominican Republic", "Caribbean", "Latin America", 48402, 5.38, 26.80, 27.54, 30.08, 2.88, 0.85, 2.72 ],
    ["Ecuador", "South America", "Latin America", 257906, 3.28, 10.57, 45.93, 34.97, 1.13, 1.36, 0.70 ],
    ["El Salvador", "Central America", "Latin America", 20935, 2.14, 39.47, 25.97, 21.74, 5.68, 0.00, 2.88 ],
    ["Equatorial Guinea", "Gulf of Guinea", "Middle East and Africa", 27132, 2.72, 6.76, 66.07, 22.34, 0.69, 0, 1.53 ],
    ["Eritrea", "Eastern Africa", "Middle East and Africa", 121045, 0.16, 5.73, 0.19, 35.21, 1.01, 54.88, 0.50 ],
    ["Estonia", "Northern Europe", "Eastern Europe", 45100, 0.03, 19.61, 48.36, 21.66, 1.35, 0.02, 6.02 ],
    ["Ethiopia", "Eastern Africa", "Middle East and Africa", 1136270, 0.26, 12.96, 7.49, 69.18, 1.85, 7.59, 0.68 ],
    ["Faroe Islands", "Northern Europe", "OECD90", 1404, 2.72, 14.80, 26.74, 31.46, 3.17, 0, 3.30 ],
    ["Fiji", "Pacific Islands", "OECD90", 18379, 0.15, 14.40, 43.96, 17.88, 1.00, 2.23, 4.52 ],
    ["Finland", "Northern Europe", "OECD90", 333683, 0.30, 6.19, 67.10, 17.17, 0.65, 0.08, 7.10 ],
    ["France", "Western Europe", "OECD90", 546661, 5.27, 30.36, 27.96, 31.61, 3.31, 0.05, 0.53 ],
    ["Gabon", "Gulf of Guinea", "Middle East and Africa", 266518, 0.02, 1.82, 81.70, 14.45, 0.22, 0.00, 0.70 ],
    ["Gambia", "Sudano-Sahelian Africa", "Middle East and Africa", 10868, 0.20, 30.87, 19.36, 37.52, 2.82, 0.01, 8.41 ],
    ["Georgia", "Central Asia", "Eastern Europe", 69623, 4.29, 10.77, 39.50, 40.32, 1.67, 2.77, 0.46 ],
    ["Germany", "Western Europe", "OECD90", 355249, 1.43, 32.33, 30.99, 26.49, 7.54, 0.00, 0.62 ],
    ["Ghana", "Gulf of Guinea", "Middle East and Africa", 240273, 0.13, 25.59, 25.36, 42.80, 2.38, 0.02, 3.36 ],
    ["Greece", "Southern Europe", "OECD90", 132389, 10.57, 17.56, 26.33, 32.92, 1.71, 0.08, 3.73 ],
    ["Grenada", "Caribbean", None, 326, 0.21, 14.80, 0.25, 0.31, 1.43, 0, 35.78 ],
    ["Guatemala", "Central America", "Latin America", 109653, 1.17, 16.71, 38.09, 39.61, 2.42, 0.11, 1.38 ],
    ["Guinea-Bissau", "Gulf of Guinea", "Middle East and Africa", 34141, 0.58, 15.03, 42.87, 30.57, 1.33, 0.00, 2.29 ],
    ["Guinea", "Gulf of Guinea", "Middle East and Africa", 246351, 0.34, 14.61, 28.01, 54.97, 1.26, 0, 0.22 ],
    ["Guyana", "South America", "Latin America", 211734, 0.58, 1.77, 84.75, 11.60, 0.11, 0.01, 0.16 ],
    ["Haiti", "Caribbean", "Latin America", 27115, 3.05, 36.56, 4.03, 39.83, 5.31, 0.40, 3.08 ],
    ["Holy See", "Southern Europe", None, 1, 1.21, 14.80, 26.74, 31.46, 98.79, 0, 3.30 ],
    ["Honduras", "Central America", "Latin America", 113398, 0.63, 15.88, 47.33, 30.92, 1.33, 0.74, 2.19 ],
    ["Hungary", "Eastern Europe", "Eastern Europe", 92743, 3.17, 48.71, 20.38, 22.56, 4.57, 0, 0.61 ],
    ["Iceland", "Northern Europe", "OECD90", 101554, 2.72, 14.80, 0.36, 70.42, 0.09, 21.55, 2.87 ],
    ["India", "Southern Asia", "Asia (Sans Japan)", 2988426, 19.04, 36.99, 22.16, 10.01, 6.94, 2.73, 1.78 ],
    ["Indonesia", "South-eastern Asia", "Asia (Sans Japan)", 1901285, 2.27, 15.73, 50.47, 23.48, 2.21, 0, 1.79 ],
    ["Iran (Islamic Republic of)", "Southern Asia", "Middle East and Africa", 1678308, 4.11, 6.21, 1.49, 19.90, 0.87, 63.44, 0.39 ],
    ["Iraq", "Western Asia", "Middle East and Africa", 436404, 8.08, 5.23, 1.15, 19.16, 1.13, 64.88, 0.35 ],
    ["Ireland", "Northern Europe", "OECD90", 69400, 0.01, 15.31, 8.54, 66.56, 1.87, 0, 2.64 ],
    ["Israel", "Western Asia", "Middle East and Africa", 20794, 8.02, 12.12, 6.43, 17.92, 4.49, 47.72, 1.37 ],
    ["Italy", "Southern Europe", "OECD90", 300854, 12.54, 23.99, 31.11, 23.73, 4.38, 0.79, 1.58 ],
    ["Jamaica", "Caribbean", "Latin America", 11085, 1.96, 22.74, 29.01, 30.32, 3.89, 0.11, 4.39 ],
    ["Japan", "Eastern Asia", "OECD90", 373363, 7.80, 4.68, 65.30, 10.08, 4.87, 0.06, 2.01 ],
    ["Jordan", "Western Asia", "Middle East and Africa", 89214, 0.83, 2.37, 0.32, 7.82, 1.00, 87.30, 0.30 ],
    ["Kazakhstan", "Central Asia", "Eastern Europe", 2828804, 0.70, 9.33, 1.20, 32.57, 0.26, 50.00, 1.69 ],
    ["Kenya", "Eastern Africa", "Middle East and Africa", 585520, 0.18, 8.46, 7.61, 79.29, 1.44, 0.72, 2.20 ],
    ["Kiribati", "Pacific Islands", None, 935, 2.72, 14.80, 26.74, 31.46, 3.17, 0, 3.30 ],
    ["Kuwait", "Western Asia", "Middle East and Africa", 17307, 0.35, 14.80, 0.01, 3.59, 3.01, 88.39, 1.35 ],
    ["Kyrgyzstan", "Central Asia", "Eastern Europe", 198768, 5.35, 1.91, 4.29, 44.23, 0.70, 40.33, 3.20 ],
    ["Lao People's Democratic Republic", "South-eastern Asia", "Asia (Sans Japan)", 231086, 1.26, 2.97, 57.16, 36.95, 0.82, 0.64, 0.20 ],
    ["Latvia", "Northern Europe", "Eastern Europe", 64082, 0.02, 15.89, 45.00, 35.55, 1.40, 0, 0.91 ],
    ["Lebanon", "Western Asia", "Middle East and Africa", 10140, 10.54, 20.37, 3.68, 52.86, 5.07, 4.56, 0.98 ],
    ["Lesotho", "Southern Africa", "Middle East and Africa", 30499, 0.07, 10.95, 0.97, 86.00, 2.01, 0, 3.30 ],
    ["Liberia", "Sudano-Sahelian Africa", "Middle East and Africa", 96480, 0.02, 7.67, 42.78, 47.10, 1.13, 0, 0.71 ],
    ["Libya", "Northern Africa", "Middle East and Africa", 1620982, 0.29, 0.27, 0.09, 2.45, 0.15, 96.56, 0.09 ],
    ["Liechtenstein", "Western Europe", None, 151, 2.72, 4.51, 54.18, 32.82, 8.49, 0, 3.30 ],
    ["Lithuania", "Northern Europe", "Eastern Europe", 64492, 0.07, 46.14, 31.17, 19.63, 2.26, 0, 0.51 ],
    ["Luxembourg", "Western Europe", "OECD90", 2609, 0.08, 19.50, 33.54, 41.58, 5.30, 0, 3.30 ],
    ["Madagascar", "Southern Africa", "Middle East and Africa", 594206, 1.80, 4.60, 21.66, 68.86, 1.03, 0.11, 0.79 ],
    ["Malawi", "Eastern Africa", "Middle East and Africa", 118741, 0.47, 22.96, 28.74, 25.39, 2.68, 0.02, 19.74 ],
    ["Malaysia", "South-eastern Asia", "Asia (Sans Japan)", 331949, 1.03, 21.48, 64.50, 8.02, 1.48, 0.00, 0.97 ],
    ["Maldives", "Southern Asia", "Asia (Sans Japan)", 185, 2.72, 14.80, 26.74, 31.46, 3.17, 0, 3.30 ],
    ["Mali", "Sudano-Sahelian Africa", "Middle East and Africa", 1257746, 0.19, 6.78, 2.76, 29.68, 0.46, 59.70, 0.43 ],
    ["Malta", "Southern Europe", "Eastern Europe", 318, 3.40, 12.05, 26.74, 16.73, 19.28, 0, 22.28 ],
    ["Marshall Islands", "Pacific Islands", None, 189, 2.72, 14.80, 26.74, 31.46, 3.17, 0, 3.30 ],
    ["Mauritania", "Sudano-Sahelian Africa", "Middle East and Africa", 1043405, 0.05, 1.02, 0.01, 12.37, 0.14, 86.17, 0.13 ],
    ["Mauritius", "Eastern Africa", "Middle East and Africa", 2022, 2.72, 14.80, 26.74, 31.46, 3.17, 0, 3.30 ],
    ["Mexico", "Central America", "Latin America", 1965060, 3.25, 10.59, 33.29, 42.13, 0.98, 7.83, 0.92 ],
    ["Micronesia (Federated States of)", "Pacific Islands", None, 694, 2.72, 14.80, 26.74, 31.46, 3.17, 0, 3.30 ],
    ["Republic of Moldova", "Eastern Europe", "Eastern Europe", 33658, 8.43, 55.89, 9.58, 21.79, 4.17, 0.00, 0.13 ],
    ["Monaco", "Western Europe", None, 7, 0.52, 12.20, 32.89, 11.59, 9.05, 0, 25.42 ],
    ["Mongolia", "Eastern Asia", "Asia (Sans Japan)", 1559230, 0.04, 0.72, 6.78, 28.97, 0.10, 62.63, 0.75 ],
    ["Morocco", "Northern Africa", "Middle East and Africa", 406760, 3.59, 17.25, 6.18, 26.28, 1.89, 43.87, 0.45 ],
    ["Mozambique", "Southern Africa", "Middle East and Africa", 791189, 0.15, 7.91, 31.50, 57.11, 0.94, 0.13, 1.65 ],
    ["Myanmar", "South-eastern Asia", "Asia (Sans Japan)", 670358, 2.66, 14.74, 51.40, 26.50, 1.69, 0.11, 1.44 ],
    ["Namibia", "Southern Africa", "Middle East and Africa", 827571, 0.01, 1.00, 1.85, 56.45, 0.17, 39.58, 0.01 ],
    ["Nauru", "Pacific Islands", None, 16, 2.72, 14.80, 26.74, 31.46, 3.17, 0, 3.30 ],
    ["Nepal", "Southern Asia", "Asia (Sans Japan)", 147646, 7.69, 9.44, 26.42, 46.73, 3.70, 5.59, 0.43 ],
    ["Netherlands", "Western Europe", "OECD90", 34992, 12.86, 18.92, 9.97, 39.13, 13.07, 0, 2.77 ],
    ["New Zealand", "Australia and New Zealand", "OECD90", 269829, 2.08, 10.16, 29.79, 47.18, 0.41, 3.25, 1.96 ],
    ["Nicaragua", "Central America", "Latin America", 129753, 0.47, 15.67, 42.51, 29.87, 1.02, 1.32, 8.24 ],
    ["Niger", "Sudano-Sahelian Africa", "Middle East and Africa", 1189554, 0.06, 2.59, 0.11, 25.28, 0.39, 71.48, 0.08 ],
    ["Nigeria", "Gulf of Guinea", "Middle East and Africa", 915038, 0.32, 37.93, 14.32, 42.69, 3.32, 0.29, 0.86 ],
    ["Niue", "Pacific Islands", None, 269, 2.72, 14.80, 26.74, 31.46, 3.17, 0, 3.30 ],
    ["Norway", "Northern Europe", "OECD90", 321212, 0.38, 2.18, 28.08, 47.74, 0.52, 11.68, 3.76 ],
    ["Oman", "Western Asia", "Middle East and Africa", 308913, 0.19, 0.00, 0.03, 0.80, 0.20, 97.36, 0.44 ],
    ["Pakistan", "Southern Asia", "Asia (Sans Japan)", 796443, 17.98, 7.85, 2.37, 21.46, 3.17, 45.62, 1.39 ],
    ["Palau", "Pacific Islands", None, 461, 2.72, 14.80, 26.74, 31.46, 3.17, 0, 3.30 ],
    ["Panama", "Central America", "Latin America", 75506, 0.46, 12.38, 55.71, 21.55, 0.95, 0.61, 3.74 ],
    ["Papua New Guinea", "Pacific Islands", "Asia (Sans Japan)", 465248, 2.72, 1.79, 63.52, 28.98, 0.47, 0.01, 1.68 ],
    ["Paraguay", "South America", "Latin America", 401177, 0.17, 13.91, 48.36, 35.60, 0.48, 0.03, 1.46 ],
    ["Peru", "South America", "Latin America", 1299324, 1.30, 1.99, 53.21, 29.22, 0.57, 12.55, 0.85 ],
    ["Philippines", "South-eastern Asia", "Asia (Sans Japan)", 297463, 4.87, 31.51, 25.54, 22.59, 4.28, 0, 3.79 ],
    ["Poland", "Eastern Europe", "Eastern Europe", 310171, 0.43, 45.72, 29.16, 20.30, 3.71, 0.00, 0.55 ],
    ["Portugal", "Southern Europe", "OECD90", 88613, 8.52, 19.81, 40.11, 26.48, 2.60, 0.00, 0.60 ],
    ["Qatar", "Western Asia", "Middle East and Africa", 11401, 1.08, 14.80, 0.00, 0.62, 2.66, 88.78, 3.51 ],
    ["Republic of Korea", "Eastern Asia", "Asia (Sans Japan)", 99048, 7.85, 10.61, 51.13, 17.60, 5.11, 0.01, 1.40 ],
    ["Romania", "Eastern Europe", "Eastern Europe", 237266, 9.05, 32.66, 27.47, 26.91, 3.22, 0.06, 0.30 ],
    ["Russian Federation", "Eastern Europe", "Eastern Europe", 16858096, 0.29, 7.19, 47.95, 33.37, 0.29, 8.40, 1.52 ],
    ["Rwanda", "Eastern Africa", "Middle East and Africa", 25367, 0.32, 44.87, 13.61, 27.48, 7.09, 0.20, 6.42 ],
    ["Saint Kitts and Nevis", "Caribbean", None, 280, 0.01, 6.14, 6.95, 11.00, 0.28, 0.47, 22.35 ],
    ["Saint Lucia", "Caribbean", None, 619, 0.33, 0.35, 39.41, 10.26, 2.41, 0, 27.14 ],
    ["Saint Vincent and the Grenadines", "Caribbean", None, 457, 2.72, 14.80, 1.64, 32.14, 1.48, 0, 21.77 ],
    ["Samoa", "Pacific Islands", "OECD90", 2892, 2.72, 14.80, 26.74, 31.46, 3.17, 0, 3.30 ],
    ["San Marino", "Southern Europe", None, 60, 1.43, 51.98, 1.51, 29.64, 7.73, 7.72, 3.30 ],
    ["Sao Tome and Principe", "Gulf of Guinea", None, 1015, 6.20, 6.86, 26.48, 22.60, 1.40, 0, 4.85 ],
    ["Saudi Arabia", "Western Asia", "Middle East and Africa", 1932471, 0.89, 0.00, 0.03, 1.50, 0.26, 97.00, 0.13 ],
    ["Senegal", "Sudano-Sahelian Africa", "Middle East and Africa", 197837, 0.59, 27.80, 7.75, 56.80, 1.39, 4.58, 0.70 ],
    ["Seychelles", "Eastern Africa", None, 450, 2.72, 14.80, 26.74, 31.46, 3.17, 0, 3.30 ],
    ["Sierra Leone", "Sudano-Sahelian Africa", "Middle East and Africa", 72810, 0.35, 27.34, 38.57, 29.12, 1.94, 0, 0.64 ],
    ["Singapore", "South-eastern Asia", "Asia (Sans Japan)", 600, 2.72, 8.12, 1.80, 8.14, 37.62, 0.19, 3.00 ],
    ["Slovakia", "Eastern Europe", "Eastern Europe", 48837, 4.56, 27.66, 39.74, 24.69, 3.29, 0, 0.06 ],
    ["Slovenia", "Southern Europe", "Eastern Europe", 20242, 0.76, 9.95, 62.01, 24.23, 2.71, 0, 0.02 ],
    ["Solomon Islands", "Pacific Islands", "OECD90", 28881, 2.72, 2.04, 64.38, 2.81, 0.38, 0, 8.29 ],
    ["Somalia", "Eastern Africa", "Middle East and Africa", 637314, 0.31, 1.14, 1.42, 63.88, 0.63, 31.56, 0.43 ],
    ["South Africa", "Southern Africa", "Middle East and Africa", 1222735, 1.22, 11.61, 7.51, 62.44, 1.37, 14.89, 0.29 ],
    ["Spain", "Southern Europe", "OECD90", 504912, 6.96, 28.93, 32.26, 27.18, 1.72, 0.86, 0.69 ],
    ["Sri Lanka", "Southern Asia", "Asia (Sans Japan)", 66596, 8.16, 24.41, 31.07, 25.18, 5.78, 0.00, 1.86 ],
    ["Suriname", "South America", "Latin America", 146967, 0.32, 0.35, 95.10, 1.45, 0.08, 0.01, 1.48 ],
    ["Swaziland", "Southern Africa", "Middle East and Africa", 17332, 2.82, 11.17, 29.81, 53.86, 2.18, 0.03, 0.13 ],
    ["Sweden", "Northern Europe", "OECD90", 445155, 0.40, 5.56, 61.39, 23.16, 1.17, 1.76, 5.19 ],
    ["Switzerland", "Western Europe", "OECD90", 41084, 0.98, 9.58, 30.04, 49.46, 4.51, 3.20, 2.23 ],
    ["Syrian Arab Republic", "Western Asia", "Middle East and Africa", 188227, 6.71, 13.00, 1.65, 20.31, 1.71, 56.22, 0.30 ],
    ["Tajikistan", "Central Asia", "Eastern Europe", 141930, 4.96, 2.46, 1.32, 27.22, 1.15, 62.47, 0.43 ],
    ["Thailand", "South-eastern Asia", "Asia (Sans Japan)", 516812, 9.57, 27.48, 28.68, 29.80, 2.82, 0.00, 0.76 ],
    ["The former Yugoslav Republic of Macedonia", "Southern Europe", "Eastern Europe", 25371, 5.02, 21.62, 35.15, 34.56, 2.11, 0, 1.54 ],
    ["Timor-Leste", "South-eastern Asia", "Asia (Sans Japan)", 14985, 0.95, 16.49, 38.86, 31.76, 1.42, 0, 2.49 ],
    ["Togo", "Gulf of Guinea", "Middle East and Africa", 57405, 0.13, 31.89, 21.52, 43.46, 2.50, 0.00, 0.44 ],
    ["Tokelau", "Pacific Islands", None, 20, 2.72, 14.80, 26.74, 31.46, 3.17, 0, 3.30 ],
    ["Tonga", "Pacific Islands", None, 668, 2.72, 14.80, 26.74, 31.46, 3.17, 0, 3.30 ],
    ["Trinidad and Tobago", "Caribbean", "Latin America", 5212, 0.58, 21.17, 40.65, 16.18, 4.06, 0.01, 5.50 ],
    ["Tunisia", "Northern Africa", "Middle East and Africa", 155258, 2.45, 9.65, 3.17, 25.78, 1.97, 55.05, 0.77 ],
    ["Turkey", "Western Asia", "OECD90", 780142, 5.30, 28.76, 12.77, 48.23, 1.78, 1.08, 1.36 ],
    ["Turkmenistan", "Central Asia", "Eastern Europe", 554371, 3.14, 0.49, 0.12, 9.49, 0.30, 71.03, 0.25 ],
    ["Tuvalu", "Pacific Islands", None, 29, 2.72, 14.80, 26.74, 31.46, 3.17, 0, 3.30 ],
    ["Uganda", "Eastern Africa", "Middle East and Africa", 242848, 0.04, 29.54, 16.79, 35.62, 2.64, 0, 15.36 ],
    ["Ukraine", "Eastern Europe", "Eastern Europe", 597677, 3.99, 51.95, 15.90, 22.76, 2.87, 0.09, 1.59 ],
    ["United Arab Emirates", "Western Asia", "Middle East and Africa", 71531, 3.79, 0.00, 0.00, 0.63, 0.99, 91.50, 0.77 ],
    ["United Kingdom", "Northern Europe", "OECD90", 242715, 0.87, 23.05, 11.11, 50.73, 6.86, 0.00, 2.63 ],
    ["United Republic of Tanzania", "Eastern Africa", "Middle East and Africa", 947127, 0.19, 12.63, 26.15, 52.47, 1.38, 0.03, 6.72 ],
    ["United States of America", "Northern America", "OECD90", 9300492, 2.99, 16.22, 32.33, 34.57, 1.43, 9.70, 2.04 ],
    ["Uruguay", "South America", "Latin America", 178309, 1.28, 10.61, 7.91, 76.55, 0.54, 0.07, 2.48 ],
    ["Uzbekistan", "Central Asia", "Eastern Europe", 448572, 9.20, 1.57, 0.42, 12.81, 1.30, 71.17, 3.52 ],
    ["Vanuatu", "Pacific Islands", "OECD90", 12290, 2.72, 7.64, 31.07, 26.09, 0.35, 0.64, 8.60 ],
    ["Venezuela (Bolivarian Republic of)", "South America", "Latin America", 917979, 0.61, 4.03, 53.42, 39.12, 0.58, 0.10, 1.35 ],
    ["Viet Nam", "South-eastern Asia", "Asia (Sans Japan)", 329159, 8.76, 17.54, 35.42, 30.87, 4.90, 0.03, 0.93 ],
    ["Yemen", "Western Asia", "Middle East and Africa", 455889, 0.85, 0.00, 0.34, 1.37, 1.03, 95.29, 0.30 ],
    ["Zambia", "Southern Africa", "Middle East and Africa", 755088, 0.21, 6.85, 41.35, 49.03, 0.71, 0.00, 1.84 ],
    ["Zimbabwe", "Eastern Africa", "Middle East and Africa", 392453, 0.44, 11.87, 31.24, 54.18, 1.46, 0.08, 0.72 ],
    ["Sudan", "Sudano-Sahelian Africa", "Middle East and Africa", 1861976, 1.00, 6.12, 0.66, 27.91, 0.56, 63.44, 0.24 ],
    ["South Sudan", "Sudano-Sahelian Africa", "Middle East and Africa", 633896, 0.01, 5.75, 14.62, 79.10, 0.51, 0, 0.01 ],
    ["Montenegro", "Southern Europe", "Eastern Europe", 13740, 0.30, 27.58, 32.08, 35.38, 1.34, 0, 2.12 ],
    ["Serbia", "Southern Europe", "Eastern Europe", 88206, 1.83, 36.14, 25.81, 32.72, 3.48, 0, 0.02 ],
    ["Egypt", "Northern Africa", "Middle East and Africa", 983657, 3.43, 0.01, 0.01, 0.25, 0.61, 94.26, 0.90 ]]
