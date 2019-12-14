import glob
import os.path
import pytest
import tempfile

import osgeo.gdal
import pandas as pd
import extract_country_data as ecd

import admin_names

pd.set_option("display.max_rows", 500)
pd.set_option("display.max_columns", 40)

def test_country_areas_reasonable():
    num = 0
    for filename in glob.glob('results/*-by-country.csv'):
        print(f"{filename}")
        num = num + 1
        df = pd.read_csv(filename).set_index('Country')
        for country, row in df.iterrows():
            if country == 'Antarctica':
                continue
            area = row.sum()
            expected = expected_area[country.upper()]
            print(f"{country}: {area} expected={expected}")
            if expected < 5000 and area < 5000:
                continue
            elif expected < 35000 and area < 35000:
                if 'workability' in filename.lower():
                    # FAO soil workability data omits a number of small countries, and is coarse
                    # enough to over-estimate a number of medium-sized countries. Just skip them,
                    # the errors are not enough to change conclusions.
                    pass
                else:
                    assert area > (expected * 0.45)
                    assert area < (expected * 1.20)
            else:
                if 'workability' in filename.lower() and country == 'Norway':
                    # FAO data is old enough that it does not reflect the resolution of the
                    # boundary dispute between Russia and Norway in 2010 which added substantial
                    # Arctic territory to Norway. Just skip it.
                    continue
                if 'fao-slope' in filename.lower() and country in ['Canada', 'Finland', 'Greenland',
                        'Iceland', 'Norway', 'Russian Federation', 'Sweden']:
                    continue
                assert area > (expected * 0.76)
                assert area < (expected * 1.07)
        print("\n")
    assert num >= 4


def test_region_areas_reasonable():
    non_aez_files = list(set(glob.glob("results/*-by-region.csv")) -
            set(glob.glob("results/AEZ-*-by-region.csv")))

    results = ['results/AEZ-*-by-region.csv'] + non_aez_files
    num = 0

    df = pd.read_csv('results/Workability-by-country.csv').set_index('Country')
    regions = ['OECD90', 'Eastern Europe', 'Asia (Sans Japan)', 'Middle East and Africa',
            'Latin America', 'China', 'India', 'EU', 'USA']
    regional = pd.DataFrame(0, index=regions, columns=['area'])
    for country, row in df.iterrows():
        region = admin_names.region_mapping[country]
        if region is not None:
            regional.loc[region, 'area'] += row.sum()

    print(str(regional))
    for g in results:
        total = pd.DataFrame(0, index=regions, columns=['area'])
        num += 1
        for filename in glob.glob(g):
            print(f"{filename}:")
            df = pd.read_csv(filename).set_index('Region')
            for region, row in df.iterrows():
                total.loc[region, 'area'] += row.sum()
        print(str(total))
        for region in regional.index:
            expected = regional.loc[region, 'area']
            actual = total.loc[region, :].sum()
            assert actual >= expected * 0.94
            assert actual <= expected * 1.05


@pytest.mark.skip(reason="Spatial result differs substantially from GAEZ 3.0")
def test_geomorpho_country_slope_vs_excel():
    df = pd.read_csv('results/Slope-by-country.csv').set_index('Country')
    gaez = pd.DataFrame(excel_slopes[1:], columns=excel_slopes[0]).set_index('Country')
    for country, row in df.iterrows():
        if country in ['Greenland', 'Taiwan', 'Western Sahara']:
            # These countries are not in the Excel data
            continue
        area = row.sum()
        if area < 30000:
            continue
        for col in df.columns:
            expected = gaez.loc[country, col]
            if expected == 0.0:
                # 0 from Excel generally means "unknown"
                continue
            actual = row[col]
            print(f"{country}:{col} {actual} <> {expected}")
            assert actual <= expected * 1000000
            assert actual >= expected * 0.1


def test_geomorpho_regional_slope_vs_GAEZ():
    df = pd.read_csv('results/Slope-by-country.csv').set_index('Country')
    gaez = pd.DataFrame(gaez_3_slopes[1:], columns=gaez_3_slopes[0]).set_index('Country')
    regions = ['OECD90', 'Eastern Europe', 'Asia (Sans Japan)', 'Middle East and Africa',
            'Latin America', 'China', 'India', 'EU', 'USA']
    df_region = pd.DataFrame(0, index=regions, columns=df.columns.copy())
    gaez_region = pd.DataFrame(0, index=regions, columns=gaez.columns.copy())
    for country, row in df.iterrows():
        region = admin_names.region_mapping[country]
        if region is not None:
            df_region.loc[region, :] += row
    for country, row in gaez.iterrows():
        region = admin_names.region_mapping[country]
        if region is not None:
            gaez_region.loc[region, :] += row

    for region in gaez_region.index:
        actual_minimal = df_region.loc[region, ["0-0.5%", "0.5-2%", "2-5%", "5-10%"]].sum()
        expected_minimal = gaez_region.loc[region, "minimal"]
        assert actual_minimal > expected_minimal * 0.8
        assert actual_minimal < expected_minimal * 1.5
        actual_moderate = df_region.loc[region, ["10-15%", "15-30%"]].sum()
        expected_moderate = gaez_region.loc[region, "moderate"]
        assert actual_moderate > expected_moderate * 0.4
        assert actual_moderate < expected_moderate * 2.0
        actual_steep = df_region.loc[region, ["30-45%", ">45%"]].sum()
        expected_steep = gaez_region.loc[region, "steep"]
        assert actual_steep > expected_steep * 0.06
        assert actual_steep < expected_steep * 1.2


@pytest.mark.skip(reason="Spatial result differs substantially from GAEZ 3.0")
def test_geomorpho_regional_slope_vs_excel():
    df = pd.read_csv('results/Slope-by-country.csv').set_index('Country')
    df_region = pd.DataFrame(0, index=['OECD90', 'Eastern Europe', 'Asia (Sans Japan)',
        'Middle East and Africa', 'Latin America', 'China', 'India', 'EU', 'USA'],
        columns=df.columns.copy())
    gaez_region = pd.DataFrame(excel_regional_slopes[1:], columns=excel_regional_slopes[0]).set_index('Region')

    for country, row in df.iterrows():
        region = admin_names.region_mapping[country]
        if region is not None:
            df_region.loc[region, :] += row
    print(str(gaez_region))
    cl_region = pd.DataFrame(0, index=df_region.index.copy(), columns=['minimal', 'moderate', 'steep'])
    cl_region['minimal'] = df_region["0-0.5%"] + df_region["0.5-2%"] + df_region["2-5%"] + df_region["5-10%"]
    cl_region['moderate'] = df_region["10-15%"] + df_region["15-30%"]
    cl_region['steep'] = df_region["30-45%"] + df_region[">45%"]
    print(str(cl_region))
    for region, expected in gaez_region.iterrows():
        minimal = df_region.loc[region, ["0-0.5%", "0.5-2%", "2-5%", "5-10%"]].sum()
        assert minimal < expected['minimal'] * 1.6
        assert minimal > expected['minimal'] * 0.4
        moderate = df_region.loc[region, ["10-15%", "15-30%"]].sum()
        assert moderate < expected['moderate'] * 1.6
        assert moderate > expected['moderate'] * 0.4
        steep = df_region.loc[region, ["30-45%", ">45%"]].sum()
        assert steep < expected['steep'] * 1.6
        assert steep < expected['steep'] * 0.4


@pytest.mark.skip(reason="Spatial result differs substantially from GAEZ 3.0")
def test_FAO_regional_slope_vs_GAEZ():
    df = pd.read_csv('results/FAO-Slope-by-country.csv').set_index('Country')
    gaez = pd.DataFrame(gaez_3_slopes[1:], columns=gaez_3_slopes[0]).set_index('Country')
    regions = ['OECD90', 'Eastern Europe', 'Asia (Sans Japan)', 'Middle East and Africa',
            'Latin America', 'China', 'India', 'EU', 'USA']
    df_region = pd.DataFrame(0, index=regions, columns=df.columns.copy())
    gaez_region = pd.DataFrame(0, index=regions, columns=gaez.columns.copy())
    for country, row in df.iterrows():
        region = admin_names.region_mapping[country]
        if region is not None:
            df_region.loc[region, :] += row
    for country, row in gaez.iterrows():
        region = admin_names.region_mapping[country]
        if region is not None:
            gaez_region.loc[region, :] += row

    for region in gaez_region.index:
        actual_minimal = df_region.loc[region, ["0-0.5%", "0.5-2%", "2-5%", "5-8%"]].sum()
        expected_minimal = gaez_region.loc[region, "minimal"]
        print(f"{region} minimal {actual_minimal} <> {expected_minimal}")
        assert actual_minimal > expected_minimal * 0.35
        assert actual_minimal < expected_minimal * 1.2
        actual_moderate = df_region.loc[region, ["8-15%", "15-30%"]].sum()
        expected_moderate = gaez_region.loc[region, "moderate"]
        print(f"{region} moderate {actual_moderate} <> {expected_moderate}")
        assert actual_moderate > expected_moderate * 0.35
        assert actual_moderate < expected_moderate * 1.2
        actual_steep = df_region.loc[region, ["30-45%", ">45%"]].sum()
        expected_steep = gaez_region.loc[region, "steep"]
        print(f"{region} steep {actual_steep} <> {expected_steep}")
        assert actual_steep > expected_steep * 0.35
        assert actual_steep < expected_steep * 1.2


def test_FAO_country_slope_vs_GAEZ():
    df = pd.read_csv('results/FAO-Slope-by-country.csv').set_index('Country')
    gaez = pd.DataFrame(gaez_3_slopes[1:], columns=gaez_3_slopes[0]).set_index('Country')
    for country, row in df.iterrows():
        if country in ['Canada', 'Finland', 'Greenland', 'Iceland', 'Norway',
                'Russian Federation', 'Sweden']:
            continue  # Truncated at 60 degrees North.
        if country in ['Cuba', 'Denmark', 'Morocco', 'Philippines', 'Western Sahara']:
            continue
        area = row.sum()
        if area < 50000:
            continue
        margin = area * 0.16

        actual_minimal = df.loc[country, ["0-0.5%", "0.5-2%", "2-5%", "5-8%"]].sum()
        expected_minimal = gaez.loc[country, 'minimal']
        print(f"{country}:minimal {actual_minimal} <> {expected_minimal}")
        assert actual_minimal <= (expected_minimal + margin)
        assert actual_minimal >= (expected_minimal - margin)

        actual_moderate = df.loc[country, ["8-15%", "15-30%"]].sum()
        expected_moderate = gaez.loc[country, 'moderate']
        print(f"{country}:moderate {actual_moderate} <> {expected_moderate}")
        assert actual_moderate <= (expected_moderate + margin)
        assert actual_moderate >= (expected_moderate - margin)

        actual_steep = df.loc[country, ["30-45%", ">45%"]].sum()
        expected_steep = gaez.loc[country, 'steep']
        print(f"{country}:steep {actual_steep} <> {expected_steep}")
        assert actual_steep <= (expected_steep + margin)
        assert actual_steep >= (expected_steep - margin)


@pytest.mark.skip(reason="Not working yet.")
def test_workability_regional():
    df = pd.read_csv('results/Workability-by-country.csv').set_index('Country')
    regions = ['OECD90', 'Eastern Europe', 'Asia (Sans Japan)', 'Middle East and Africa',
            'Latin America', 'China', 'India', 'EU', 'USA']
    df_region = pd.DataFrame(0, index=regions, columns=df.columns.copy())
    health = pd.DataFrame(0, index=regions, columns=['soil', 'bare'])
    for country, row in df.iterrows():
        region = admin_names.region_mapping[country]
        if region is not None:
            df_region.loc[region, :] += row
            health.loc[region, 'soil'] += row['1'] + row['2'] + row['3'] + row['4']
            health.loc[region, 'bare'] += row['5'] + row['6'] + row['7']
    print(str(df_region))
    print(str(health))
    assert False


def test_kg():
    shapefilename = 'data/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp'
    mapfilename = 'data/Beck_KG_V1/Beck_KG_V1_present_0p5.tif'
    lookupobj = ecd.KGlookup(mapfilename, maskdim='0p5')
    csvfile = tempfile.NamedTemporaryFile()
    assert os.path.getsize(csvfile.name) == 0
    ecd.process_map(lookupobj=lookupobj, csvfilename=csvfile.name)
    assert os.path.getsize(csvfile.name) != 0
    df = pd.read_csv(csvfile.name).set_index('Country').sum(axis=1)
    assert 'United States of America' in df.index
    assert df['United States of America'] > 1

def test_lc():
    shapefilename = 'data/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp'
    mapfilename = 'data/copernicus/test_small.tif'
    lookupobj = ecd.ESA_LC_lookup(mapfilename, maskdim='0p5')
    csvfile = tempfile.NamedTemporaryFile()
    assert os.path.getsize(csvfile.name) == 0
    ecd.process_map(lookupobj=lookupobj, csvfilename=csvfile.name)
    assert os.path.getsize(csvfile.name) != 0
    df = pd.read_csv(csvfile.name).set_index('Country').sum(axis=1)
    assert 'United States of America' in df.index
    assert df['United States of America'] > 1

def test_sl():
    shapefilename = 'data/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp'
    mapfilename = 'data/geomorpho90m/test_small.tif'
    lookupobj = ecd.GeomorphoLookup(mapfilename, maskdim='0p5')
    csvfile = tempfile.NamedTemporaryFile()
    assert os.path.getsize(csvfile.name) == 0
    ecd.process_map(lookupobj=lookupobj, csvfilename=csvfile.name)
    assert os.path.getsize(csvfile.name) != 0
    df = pd.read_csv(csvfile.name).set_index('Country').sum(axis=1)
    assert 'United States of America' in df.index
    assert df['United States of America'] > 1

def test_wk():
    shapefilename = 'data/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp'
    mapfilename = 'data/FAO/test_small.tif'
    lookupobj = ecd.WorkabilityLookup(mapfilename, maskdim='0p5')
    csvfile = tempfile.NamedTemporaryFile()
    assert os.path.getsize(csvfile.name) == 0
    ecd.process_map(lookupobj=lookupobj, csvfilename=csvfile.name)
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


# Slope data from "WORLD Land Data" tab of Afforestation Excel file of 6.2019
excel_slopes = [
    ["Country", "0-0.5%", "0.5-2%", "15-30%", "2-5%", "30-45%", "5-10%", "10-15%", ">45%", "Undefined", "Water"],
    ["Afghanistan",  682,  3827,  135575,  70448,  144666,  82193,  111672,  91515,  0,  1144],
    ["Albania",  5,  428,  7380,  1102,  14105,  667,  1486,  3015,  7,  236],
    ["Algeria",  163486,  532000,  206210,  588849,  64158,  332330,  420925,  13457,  2,  290],
    ["Andorra", 0,  0,  0,  0,  169,  0,  0,  307,  0,  0],
    ["Angola",  2059, 32909, 342033, 196140, 28312, 211003, 436930, 4820, 13, 407],
    ["Antigua and Barbuda",  447, 0, 0, 0, 0, 0, 0, 0, 2, 0],
    ["Argentina",  22170, 374604, 285533, 912191, 151739, 535604, 420414, 57534, 8, 20732],
    ["Armenia",  65, 164, 10314, 788, 11480, 823, 3459, 1391, 0, 1112],
    ["Australia",  829867, 3425706, 119115, 2300595, 14437, 607823, 317666, 841, 167, 92939],
    ["Austria",  0, 322, 12867, 3314, 21524, 4348, 17254, 23774, 0, 216],
    ["Azerbaijan",  1830, 7137, 16122, 15619, 16372, 8668, 15495, 4816, 0, 78632],
    ["Bahamas",  1883, 7203, 0, 3547, 0, 207, 0, 0, 64, 472],
    ["Bahrain",  0, 100, 0, 218, 0, 280, 77, 0, 1, 0],
    ["Bangladesh",  20475, 68612, 4297, 29946, 1111, 6448, 4970, 0, 118, 3344],
    ["Barbados",  0, 0, 143, 0, 0, 4, 297, 0, 0, 0],
    ["Belarus",  99, 1936, 0, 152060, 0, 51196, 856, 0, 0, 146],
    ["Belgium",  1402, 5324, 1491, 4670, 0, 7391, 10231, 0, 0, 0],
    ["Belize",  1447, 6029, 3864, 5636, 659, 1423, 3248, 0, 17, 42],
    ["Benin",  7379, 36380, 0, 49908, 0, 18211, 4403, 0, 0, 0],
    ["Bhutan",  0, 0, 874, 12, 5699, 140, 378, 30659, 0, 0],
    ["Bolivia",  102374, 297116, 139471, 251228, 100616, 83791, 88698, 17764, 0, 8762],
    ["Bosnia and Herzegovina",  0, 334, 23444, 2063, 16054, 1342, 6908, 854, 0, 0],
    ["Botswana",  30511, 145883, 3797, 234568, 154, 114114, 51253, 0, 0, 0],
    ["Brazil",  1068647, 1825601, 185514, 2593462, 8412, 1681720, 1090968, 99, 88, 78234],
    ["Brunei Darussalam",  816, 367, 416, 1280, 90, 2083, 849, 0, 0, 0],
    ["Bulgaria",  52, 435, 37487, 4870, 14939, 11289, 40495, 798, 0, 653],
    ["Burkina Faso",  12133, 50263, 1090, 69851, 0, 99236, 42399, 0, 0, 0],
    ["Burundi",  216, 142, 8455, 428, 4654, 2513, 8248, 743, 0, 1731],
    ["Cambodia",  8338, 29254, 16446, 54453, 5313, 44432, 21237, 84, 6, 2935],
    ["Cameroon",  10766, 50533, 40478, 143155, 6775, 108862, 105446, 512, 0, 2744],
    ["Canada",  399684, 1921057, 976518, 2352373, 436825, 1602909, 1547356, 197094, 785, 371599],
    ["Cape Verde",  77, 52, 1041, 117, 1294, 106, 1161, 228, 1, 0],
    ["Central African Republic",  21555, 173104, 1253, 234941, 0, 114395, 77423, 0, 0, 1531],
    ["Chad",  79883, 375258, 83540, 272846, 23665, 227419, 193524, 6673, 0, 13839],
    ["Chile",  7395, 4722, 258171, 37976, 154553, 61511, 144033, 75427, 136, 9762],
    ["China",  29110, 274750, 2400323, 1251526, 1641614, 1219498, 1814103, 680262, 72, 67557],
    ["Colombia",  83839, 250064, 144587, 333932, 126062, 116107, 77323, 11492, 53, 1925],
    ["Comoros",  9, 0, 609, 0, 841, 15, 11, 200, 0, 0],
    ["Congo",  19725, 136868, 1864, 114294, 0, 45100, 23823, 0, 1, 2206],
    ["Cook Islands",  57, 5, 67, 25, 4, 25, 60, 0, 5, 0],
    ["Costa Rica",  55, 2266, 14455, 5361, 12887, 4962, 8045, 3444, 32, 31],
    ["Croatia",  31, 1329, 18870, 10816, 4990, 6562, 13683, 95, 6, 0],
    ["Cuba",  7643, 21094, 9950, 34053, 4415, 18727, 15397, 329, 56, 163],
    ["Cyprus",  0, 0, 2467, 13, 2697, 928, 1727, 1179, 0, 0],
    ["Czech Republic",  0, 165, 18085, 2478, 941, 11643, 45149, 0, 0, 0],
    ["Côte d'Ivoire",  11942, 73694, 3244, 137744, 10, 61717, 32935, 0, 0, 2654],
    ["Democratic People's Republic of Korea",  311, 1078, 38154, 2413, 60497, 4954, 14233, 454, 3, 207],
    ["Democratic Republic of the Congo",  213199, 611260, 282820, 496891, 29169, 278720, 388226, 971, 0, 42287],
    ["Denmark",  760, 5309, 2, 20014, 0, 15003, 1438, 0, 9, 1590],
    ["Djibouti",  0, 12, 8892, 188, 5367, 1314, 4502, 1285, 0, 258],
    ["Dominica",  770, 0, 0, 0, 0, 0, 0, 0, 1, 0],
    ["Dominican Republic",  248, 965, 13703, 5607, 9270, 6556, 10664, 977, 2, 408],
    ["Ecuador",  4946, 47500, 55262, 41551, 40470, 28626, 36661, 2885, 4, 0],
    ["El Salvador",  18, 479, 10881, 1083, 3120, 1200, 4071, 9, 22, 52],
    ["Equatorial Guinea",  0, 1665, 1433, 11646, 911, 6895, 4394, 172, 15, 0],
    ["Eritrea",  37, 379, 36518, 2764, 26446, 17184, 25404, 12290, 22, 0],
    ["Estonia",  178, 2422, 0, 36970, 0, 3561, 108, 0, 2, 1859],
    ["Ethiopia",  1708, 16540, 267416, 112677, 106858, 224871, 329590, 69023, 0, 7588],
    ["Faroe Islands",  0, 1, 1029, 0, 304, 12, 57, 0, 0, 0],
    ["Fiji", 755, 174, 7212, 458, 770, 1265, 7538, 172, 34, 0],
    ["Finland", 1484, 1730, 3104, 97337, 0, 148259, 55430, 0, 16, 26322],
    ["France", 2162, 11259, 74584, 71511, 33416, 141956, 189410, 21836, 15, 514],
    ["Gabon", 6433, 39793, 3301, 127809, 0, 64035, 23058, 0, 4, 2085],
    ["Gambia", 0, 0, 0, 812, 0, 6602, 3115, 0, 0, 340],
    ["Georgia", 6, 1467, 14974, 2830, 16903, 2547, 8956, 21940, 0, 0],
    ["Germany", 4485, 48263, 50390, 83512, 4551, 53734, 108479, 1223, 6, 607],
    ["Ghana", 10699, 61900, 2897, 79841, 85, 48783, 24138, 0, 0, 11929],
    ["Greece", 56, 2086, 42880, 5267, 46928, 4351, 13623, 16808, 224, 167],
    ["Grenada",  6, 0, 200, 0, 106, 0, 13, 0, 0, 0],
    ["Guatemala",  515, 5568, 23392, 21815, 24908, 13703, 14395, 5146, 13, 198],
    ["Guinea-Bissau",  58, 74, 970, 2238, 0, 7347, 23446, 0, 7, 0],
    ["Guinea",  1246, 17273, 48284, 39196, 1594, 38708, 100049, 0, 0, 0],
    ["Guyana",  8917, 47885, 4116, 59542, 223, 50435, 40326, 0, 0, 290],
    ["Haiti",  174, 616, 11370, 714, 8780, 1017, 3919, 437, 6, 81],
    ["Holy See",  0, 0, 0, 0, 0, 1, 0, 0, 0, 0],
    ["Honduras",  1399, 3277, 41708, 8122, 35549, 7114, 13567, 1090, 10, 1562],
    ["Hungary",  1791, 18966, 5284, 33036, 0, 14519, 18402, 0, 0, 745],
    ["Iceland",  42, 1293, 27338, 8557, 13768, 15953, 33487, 778, 8, 329],
    ["India",  34398, 455888, 242318, 847647, 111814, 777454, 429915, 82296, 150, 6547],
    ["Indonesia",  191884, 294064, 420486, 316777, 147065, 205181, 310961, 10473, 352, 4041],
    ["Iran",  12930, 8389, 425804, 124611, 275289, 198932, 374211, 193558, 11, 64573],
    ["Iraq",  4326, 9098, 18218, 146079, 8827, 157127, 78978, 13315, 0, 434],
    ["Ireland",  1676, 9304, 7075, 16873, 197, 17551, 15712, 0, 10, 1002],
    ["Israel",  65, 0, 10020, 75, 2358, 807, 7230, 1, 0, 237],
    ["Italy",  18547, 8583, 86151, 20788, 62431, 20912, 42774, 39447, 74, 1148],
    ["Jamaica",  0, 8, 6624, 742, 1004, 294, 2167, 245, 0, 0],
    ["Japan",  2531, 7610, 154602, 17651, 94937, 26783, 55658, 13418, 34, 139],
    ["Jordan",  8, 0, 8643, 7531, 7085, 25266, 37077, 2859, 0, 745],
    ["Kazakhstan",  20685, 158891, 74834, 1315719, 50022, 791065, 221812, 15858, 0, 179918],
    ["Kenya",  2910, 49065, 63466, 111370, 12184, 169938, 161530, 3871, 1, 11185],
    ["Kiribati",  892, 5, 0, 8, 0, 9, 0, 0, 21, 0],
    ["Kuwait",  0, 749, 0, 3434, 0, 12182, 942, 0, 0, 0],
    ["Kyrgyzstan",  191, 0, 36032, 2528, 64527, 4616, 17120, 66784, 0, 6970],
    ["Lao People's Democratic Republic",  163, 29, 65707, 12677, 100676, 21828, 24575, 5432, 0, 0],
    ["Latvia",  5, 672, 0, 50372, 0, 12660, 279, 0, 0, 94],
    ["Lebanon",  0, 0, 1689, 6, 4910, 413, 550, 2568, 2, 0],
    ["Lesotho",  0, 0, 3270, 0, 4931, 0, 1, 22297, 0, 0],
    ["Liberia",  1652, 17540, 464, 41196, 0, 21226, 14401, 0, 0, 0],
    ["Libya",  33931, 282332, 102776, 324873, 10958, 432770, 432203, 1135, 4, 0],
    ["Liechtenstein",  0, 0, 47, 0, 3, 7, 0, 95, 0, 0],
    ["Lithuania",  0, 1244, 0, 42920, 0, 19644, 606, 0, 0, 78],
    ["Luxembourg",  0, 0, 722, 0, 0, 245, 1642, 0, 0, 0],
    ["Madagascar",  1460, 25292, 174079, 57856, 41943, 89587, 198894, 4513, 11, 571],
    ["Malawi",  558, 1171, 19558, 13278, 3467, 24085, 30996, 828, 0, 24799],
    ["Malaysia",  13176, 19275, 73841, 56999, 22277, 65664, 79781, 908, 27, 0],
    ["Maldives",  127, 0, 0, 0, 0, 0, 0, 0, 58, 0],
    ["Mali",  232103, 523167, 14473, 222638, 499, 142369, 120762, 0, 0, 1736],
    ["Malta",  3, 0, 180, 0, 0, 0, 134, 0, 1, 0],
    ["Marshall Islands",  130, 3, 0, 0, 0, 0, 0, 0, 56, 0],
    ["Mauritania",  168588, 534594, 7685, 177152, 243, 87379, 67760, 0, 2, 2],
    ["Mauritius",  34, 140, 452, 243, 0, 602, 536, 7, 8, 0],
    ["Mexico",  36942, 144278, 489489, 236156, 337042, 244558, 373815, 94909, 179, 7693],
    ["Micronesia (Federated States of)",  55, 8, 339, 14, 0, 8, 252, 0, 18, 0],
    ["Moldova",  266, 316, 5130, 480, 0, 1553, 25909, 0, 0, 5],
    ["Monaco",  0, 0, 1, 0, 7, 0, 0, 0, 0, 0],
    ["Mongolia",  1744, 5664, 368487, 106973, 124460, 466822, 466797, 6681, 0, 11601],
    ["Morocco",  70, 1839, 113849, 10701, 84854, 37511, 114213, 43575, 1, 145],
    ["Mozambique",  7146, 60290, 88035, 195576, 13080, 206844, 208505, 2728, 23, 8962],
    ["Myanmar",  1356, 21763, 150249, 98079, 163221, 83024, 111054, 41102, 31, 479],
    ["Namibia",  314, 9583, 134432, 154883, 43249, 244687, 229114, 11304, 5, 0],
    ["Nauru",  0, 0, 0, 0, 0, 16, 0, 0, 0, 0],
    ["Nepal",  0, 6579, 9690, 9649, 44350, 4705, 5053, 67621, 0, 0],
    ["Netherlands",  17435, 13383, 0, 1614, 0, 778, 155, 0, 0, 1628],
    ["New Zealand",  3167, 3145, 83643, 12171, 58635, 19202, 72278, 14358, 21, 3209],
    ["Nicaragua",  1105, 7678, 32116, 16983, 7189, 26767, 28373, 0, 38, 9505],
    ["Niger",  132134, 515416, 17280, 201953, 81, 165341, 154287, 0, 0, 3062],
    ["Nigeria",  30846, 203767, 30028, 289629, 4136, 200791, 145268, 169, 3, 10400],
    ["Niue",  0, 12, 0, 178, 0, 79, 0, 0, 0, 0],
    ["Norway",  76, 88, 149254, 1597, 73339, 13008, 65663, 12589, 17, 5582],
    ["Oman",  5807, 5966, 40980, 51411, 22137, 100752, 69060, 12800, 1, 0],
    ["Pakistan",  4260, 137463, 142203, 163883, 66904, 110037, 128999, 41999, 1, 693],
    ["Palau",  56, 22, 0, 63, 0, 61, 256, 0, 2, 0],
    ["Panama",  506, 1276, 24575, 6432, 11752, 10300, 19250, 969, 21, 425],
    ["Papua New Guinea",  14348, 45196, 109807, 84785, 86413, 51034, 62619, 8781, 21, 2244],
    ["Paraguay",  14854, 164321, 9674, 95879, 77, 25931, 88398, 0, 0, 2044],
    ["Peru",  171698, 226791, 258933, 132487, 173352, 88019, 186410, 46597, 2, 15035],
    ["Philippines",  1417, 10046, 100300, 21447, 70034, 24508, 56870, 11361, 229, 1251],
    ["Poland",  1034, 8568, 13655, 177163, 1405, 84480, 22654, 120, 0, 1091],
    ["Portugal",  113, 190, 32494, 1667, 7053, 11146, 35885, 65, 1, 0],
    ["Qatar",  13, 413, 0, 6763, 0, 4022, 163, 0, 3, 23],
    ["Republic of Korea (South Korea)",  91, 267, 46797, 2591, 24986, 5310, 18707, 276, 24, 0],
    ["Romania",  2498, 9221, 73273, 34239, 30448, 30964, 54361, 1740, 0, 522],
    ["Russian Federation",  93390, 519139, 3255392, 3802235, 1276926, 3983256, 3603418, 97658, 858, 225824],
    ["Rwanda",  104, 34, 7343, 0, 13518, 43, 200, 2144, 0, 1980],
    ["Saint Kitts and Nevis",  280, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    ["Saint Lucia",  0, 3, 331, 0, 151, 28, 106, 0, 0, 0],
    ["Saint Vincent and the Grenadines",  4, 0, 211, 0, 175, 13, 17, 37, 0, 0],
    ["Samoa",  57, 0, 1696, 71, 511, 65, 491, 0, 1, 0],
    ["San Marino",  0, 0, 57, 0, 0, 0, 3, 0, 0, 0],
    ["Sao Tome and Principe",  0, 0, 410, 82, 256, 116, 150, 0, 3, 0],
    ["Saudi Arabia",  10551, 118967, 294372, 206452, 100360, 536614, 626530, 38534, 76, 15],
    ["Senegal",  8785, 33128, 1309, 52828, 0, 61272, 39588, 0, 4, 924],
    ["Seychelles",  44, 139, 51, 34, 91, 11, 60, 0, 20, 0],
    ["Sierra Leone",  1, 4916, 3038, 16467, 596, 20570, 27049, 0, 3, 171],
    ["Singapore",  403, 157, 0, 39, 0, 2, 0, 0, 0, 0],
    ["Slovakia",  0, 644, 22114, 6252, 7019, 3445, 9035, 328, 0, 0],
    ["Slovenia",  0, 59, 8908, 671, 4305, 1007, 3654, 1636, 0, 0],
    ["Solomon Islands",  2204, 540, 15035, 849, 3053, 1062, 6039, 93, 7, 0],
    ["Somalia",  21809, 145824, 53946, 129988, 25280, 133213, 117064, 10186, 3, 0],
    ["South Africa",  1, 303, 338158, 38422, 190871, 202879, 390910, 58961, 9, 2221],
    ["Spain",  238, 2218, 171822, 20246, 69300, 50910, 172173, 17479, 4, 522],
    ["Sri Lanka",  1128, 6492, 6662, 24681, 2904, 14684, 9737, 0, 4, 304],
    ["Suriname",  8028, 30004, 5198, 43857, 86, 35111, 21404, 0, 1, 3279],
    ["Swaziland",  0, 0, 7243, 0, 7982, 0, 767, 1340, 0, 0],
    ["Sweden",  848, 2429, 50467, 48160, 5070, 125959, 191535, 488, 13, 20185],
    ["Switzerland",  52, 0, 9447, 421, 4936, 274, 4657, 20326, 0, 971],
    ["Syrian Arab Republic",  140, 213, 19361, 18621, 6222, 72567, 69616, 1374, 3, 110],
    ["Tajikistan",  327, 67, 20397, 3398, 28809, 3676, 9760, 75029, 0, 467],
    ["Thailand",  8987, 27194, 114152, 146600, 52284, 98280, 68456, 417, 24, 419],
    ["The former Yugoslav Republic of Macedonia",  62, 0, 10009, 842, 10072, 342, 2756, 863, 0, 425],
    ["Timor-Leste",  0, 13, 8623, 44, 2097, 543, 3618, 45, 3, 0],
    ["Togo",  2585, 14972, 2015, 18970, 0, 11191, 7608, 0, 0, 64],
    ["Tokelau",  0, 0, 0, 0, 0, 0, 0, 0, 20, 0],
    ["Tonga",  466, 23, 93, 6, 55, 6, 8, 2, 10, 0],
    ["Trinidad and Tobago",  113, 85, 808, 2174, 149, 1143, 737, 0, 3, 0],
    ["Tunisia",  1770, 7766, 24448, 38431, 5041, 35167, 42422, 73, 4, 137],
    ["Turkey",  1153, 2655, 292687, 23656, 194876, 37328, 140687, 78231, 9, 8860],
    ["Turkmenistan",  1764, 81081, 15802, 235192, 3699, 83601, 48948, 137, 0, 84149],
    ["Tuvalu",  22, 3, 0, 0, 0, 0, 0, 0, 3, 0],
    ["Uganda",  1563, 5076, 34253, 28985, 11117, 41166, 81729, 1180, 0, 37778],
    ["Ukraine",  5937, 6769, 14934, 183009, 9595, 217113, 154487, 23, 17, 5795],
    ["United Arab Emirates",  36, 0, 6210, 6770, 2379, 29917, 24761, 1449, 9, 0],
    ["United Kingdom",  6941, 30844, 29498, 53954, 2138, 52187, 66242, 0, 19, 894],
    ["United Republic of Tanzania",  8047, 54087, 112711, 189070, 22449, 218264, 284157, 1455, 10, 56878],
    ["United States of America",  242086, 614486, 1563724, 1707997, 810472, 2114583, 1962130, 213793, 1230, 69990],
    ["Uruguay",  1140, 9943, 4890, 12881, 0, 57347, 88805, 0, 6, 3296],
    ["Uzbekistan",  8570, 65687, 18977, 183195, 13649, 79577, 38348, 8658, 0, 31910],
    ["Vanuatu",  429, 30, 5436, 415, 2090, 558, 3193, 135, 5, 0],
    ["Venezuela",  49598, 180143, 104867, 182822, 33074, 126889, 229042, 5020, 14, 6511],
    ["Vietnam",  43948, 13543, 71227, 23174, 90944, 22955, 44392, 18909, 67, 0],
    ["Yemen",  92, 5981, 135798, 20068, 90970, 52693, 105128, 45148, 11, 0],
    ["Zambia",  2456, 49574, 71463, 192052, 8306, 179693, 239731, 511, 0, 11300],
    ["Zimbabwe",  86, 23385, 110969, 39788, 30714, 49069, 129301, 5490, 0, 3652],
    ["Sudan",  21068, 195451, 118871, 415788, 27614, 654230, 421387, 5926, 22, 1619],
    ["South Sudan",  20067, 176723, 12851, 231138, 3268, 85700, 102182, 1118, 0, 849],
    ["Montenegro",  15, 15, 5247, 190, 6890, 91, 316, 713, 0, 263],
    ["Serbia",  0, 8069, 31493, 13911, 13661, 4400, 16092, 580, 0, 0],
    ["Egypt",  38744, 59358, 114628, 110309, 26954, 251709, 369800, 7963, 12, 4178]]

excel_regional_slopes = [
    ["Region", "minimal", "moderate", "steep"],
    ["OECD90", 19627570, 9109168, 2634982],
    ["Eastern Europe", 12784219, 8147218, 1923724],
    ["Asia (Sans Japan)", 8436584, 8315608, 4068697],
    ["Middle East and Africa", 20667451, 11941423, 2022923],
    ["Latin America", 13530917, 5149723, 1569761],
    ["China", 2774884, 4214426, 2321876],
    ["India", 2115386, 672233, 194111],
    ["EU", 1932127, 1863591, 441280],
    ["USA", 4679152, 3525854, 1024266]]

# Data from http://www.gaez.iiasa.ac.at
gaez_3_slopes = [
    ["Country", "minimal", "moderate", "steep"],
    ["Afghanistan",307752,160287.5,173110.5],
    ["Albania",7870.2,11199.9,11502.6],
    ["Algeria",2070015.4,186068.8,23258.6],
    ["Angola",1127558.8,114022.8,12669.2],
    ["Argentina",2329278.8,280636,168381.6],
    ["Armenia",11301.2,10409,8029.8],
    ["Australia",7335737.7,394394.5,78878.9],
    ["Austria",27512.1,23343.6,32514.3],
    ["Azerbaijan",55855.8,19819.8,13513.5],
    ["Bahamas",32267.2,0,0],
    ["Bangladesh",138415,5890,1472.5],
    ["Belarus",204256.8,2063.2,0],
    ["Belgium",27278.5,3065,306.5],
    ["Belize",20717.6,3816.4,1090.4],
    ["Benin",114062.2,2327.8,0],
    ["Bhutan",1136.7,5683.5,30690.9],
    ["Bolivia",807562,141869,141869],
    ["Bosnia and Herzegovina",16846.5,22972.5,11231],
    ["Botswana",581400,0,0],
    ["Brazil",7138589.3,1204099.4,258021.3],
    ["Bulgaria",63840,34720,14560],
    ["Burkina Faso",272408.4,0,0],
    ["Burundi",10720,12596,3216],
    ["Cambodia",163970.4,18633,5589.9],
    ["Cameroon",372872.1,84958.2,18879.6],
    ["Canada",7245379.6,2245047.2,714333.2],
    ["Central African Republic",593056.5,24970.8,0],
    ["Chad",1200069.8,51066.8,12766.7],
    ["Chile",350238.4,230644.8,247729.6],
    ["China",5193166,2266108.8,1888424],
    ["Colombia",834544.8,173863.5,162272.6],
    ["Democratic Republic of the Congo",1991762.5,328055,23432.5],
    ["Congo",286159.1,55163.2,3447.7],
    ["Costa Rica",28645.4,18707.2,10522.8],
    ["Côte d'Ivoire",306825.4,16320.5,3264.1],
    ["Croatia",39161.6,20931.2,6752],
    ["Cuba",120464.4,11472.8,4302.3],
    ["Cyprus",6720,3600,1320],
    ["Czech Republic",54733,21893.2,1563.8],
    ["Denmark",54662.4,569.4,0],
    ["Djibouti",15403.3,5287.7,2069.1],
    ["Dominican Republic",32774.5,14443,7777],
    ["Ecuador",135595,73221.3,59661.8],
    ["Egypt",909590.5,59973,19991],
    ["El Salvador",11188.8,8391.6,3263.4],
    ["Equatorial Guinea",19046.4,8630.4,2083.2],
    ["Eritrea",85772.8,26804,20103],
    ["Estonia",49896.8,514.4,0],
    ["Ethiopia",750624.6,261581.3,113731],
    ["Fiji",13209,14637,4641],
    ["Finland",247442.1,97582.8,0],
    ["France",410698,101268,45008],
    ["French Guiana",57566.4,26635.2,859.2],
    ["French Polynesia",14658.8,2819,3382.8],
    ["Gabon",176533.5,84192.9,8147.7],
    ["Gambia",11475.8,0,0],
    ["Georgia",21348,19213.2,29887.2],
    ["Germany",291000,58200,10912.5],
    ["Ghana",225813.3,14568.6,2428.1],
    ["Greece",62940.5,66537.1,43159.2],
    ["Greenland",1809005.4,312667.6,67000.2],
    ["Guatemala",60420.6,31329.2,21259.1],
    ["Guinea",191522.1,52233.3,7461.9],
    ["Guinea-Bissau",39100.8,407.3,0],
    ["Guyana",172272,36607.8,6460.2],
    ["Haiti",14271.6,11893,6796],
    ["Honduras",45094.6,43907.9,28480.8],
    ["Hungary",82414,9260,926],
    ["Iceland",37973.1,54082.9,20712.6],
    ["India",2575593.5,272709.9,181806.6],
    ["Indonesia",1348539.2,530572.8,309500.8],
    ["Iran",1081245,360415,196590],
    ["Iraq",410065.6,17449.6,8724.8],
    ["Ireland",62743.2,12870.4,2413.2],
    ["Israel",16155,4523.4,646.2],
    ["Italy",144984.4,105443.2,75787.3],
    ["Jamaica",6744,5198.5,1686],
    ["Japan",157531.5,157531.5,117023.4],
    ["Jordan",78311.2,8009.1,2669.7],
    ["Kazakhstan",2558153.6,108857.6,54428.8],
    ["Kenya",517809.6,52957.8,17652.6],
    ["Democratic People's Republic of Korea",32495,48092.6,46792.8],
    ["Republic of Korea (South Korea)",38857.6,44929.1,31571.8],
    ["Kuwait",18671.4,0,0],
    ["Kyrgyzstan",49760,53740.8,93548.8],
    ["Lao People's Democratic Republic",74108.8,81056.5,76424.7],
    ["Latvia",64835.1,1309.8,0],
    ["Lebanon",3962,5094,2377.2],
    ["Lesotho",5825.4,13183.8,11650.8],
    ["Liberia",82236.4,15852.8,990.8],
    ["Libya",1562928,48841.5,0],
    ["Lithuania",63651,649.5,0],
    ["Macedonia",7632,10430.4,7377.6],
    ["Madagascar",385646.2,186603,49760.8],
    ["Malawi",94920,17797.5,4746],
    ["Malaysia",186898.4,111420.2,57507.2],
    ["Mali",1232800.8,25159.2,0],
    ["Mauritania",1036579.5,10470.5,0],
    ["Mexico",1216956,466499.8,304239],
    ["Moldova",26504.5,7381,0],
    ["Mongolia",1136887.4,327049.8,93442.8],
    ["Montenegro",3367.2,6032.9,4629.9],
    ["Morocco",273490.8,99451.2,45581.8],
    ["Mozambique",743976.4,48520.2,16173.4],
    ["Myanmar",330668.5,196994,182923],
    ["Namibia",758921.8,58378.6,25019.4],
    ["Nepal",31012.8,26582.4,90084.8],
    ["Netherlands",39062.8,0,0],
    ["New Caledonia",13160.4,8075.7,6580.2],
    ["New Zealand",110329.2,95005.7,91941],
    ["Nicaragua",94311,32335.2,8083.8],
    ["Niger",1164828,23772,0],
    ["Nigeria",863775.4,36756.4,18378.2],
    ["Norway",66403.8,191833.2,106983.9],
    ["Oman",274959.2,31972,15986],
    ["Pakistan",601200,112224,88176],
    ["Panama",45260,29871.6,13578],
    ["Papua New Guinea",272452.2,138897.2,117528.4],
    ["Paraguay",396782.1,4007.9,0],
    ["Peru",710267.4,289368.2,315674.4],
    ["Philippines",188925.9,124610.7,72354.6],
    ["Poland",290373.9,15611.5,3122.3],
    ["Portugal",57739.5,27495,5499],
    ["Puerto Rico",6523.2,3986.4,1208],
    ["Qatar",13465.2,0,0],
    ["Romania",135511.8,73699.4,28528.8],
    ["Russian Federation",10365327.4,5097702,1189463.8],
    ["Rwanda",9104.4,11886.3,4552.2],
    ["Saudi Arabia",1739861,156392,58647],
    ["Senegal",198960.3,0,0],
    ["Serbia",46735.4,29099.4,12345.2],
    ["Sierra Leone",58758.7,13735.8,3052.4],
    ["Slovakia",23366.4,18011.6,7302],
    ["Slovenia",6600,8200,5200],
    ["Solomon Islands",24763.2,18009.6,9004.8],
    ["Somalia",607169.1,32643.5,13057.4],
    ["South Africa",990272,198054.4,61892],
    ["South Sudan",614718.1,12674.6,0],
    ["Spain",305787.6,152893.8,63266.4],
    ["Sri Lanka",59464,9662.9,4459.8],
    ["Sudan",1809690.2,55969.8,18656.6],
    ["Suriname",116251.2,28317.6,4471.2],
    #["Svalbard and Jan Mayen Isl",26027,35213,13013.5],
    ["Swaziland",9997.8,6314.4,1403.2],
    ["Sweden",241810.4,199958.6,18600.8],
    ["Switzerland",10618.4,11026.8,19194.8],
    ["Syrian Arab Republic",173447.6,11311.8,1885.3],
    ["Tajikistan",32574.9,33991.2,76480.2],
    ["United Republic of Tanzania",812234.5,114668.4,28667.1],
    ["Thailand",370219.5,101944.5,59020.5],
    ["Timor-Leste",5932.8,8713.8,3522.6],
    ["Togo",53369.2,4060.7,580.1],
    ["Tunisia",140792.1,16183,1618.3],
    ["Turkey",345646.9,305455.4,152727.7],
    ["Turkmenistan",467951,19703.2,4925.8],
    ["Uganda",208885.4,26717.9,7286.7],
    ["Ukraine",559258.8,36473.4,6078.9],
    ["United Arab Emirates",72208.5,3967.5,1587],
    ["United Kingdom",198253.3,64222.9,13961.5],
    ["United States of America",6476782.4,2000182.8,952468],
    ["Uruguay",173166,5468.4,0],
    ["Uzbekistan",407470.7,22388.5,17910.8],
    ["Vanuatu",11601,7991.8,4382.6],
    ["Venezuela",685148.8,178326.4,75084.8],
    ["Vietnam",170941.4,90703.6,87215],
    ["Yemen",310939.2,108357.6,56534.4],
    ["Zambia",709737.6,30201.6,7550.4],
    ["Zimbabwe",349058,35298,11766]]
