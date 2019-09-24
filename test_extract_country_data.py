import glob
import os.path
import pytest
import tempfile

import osgeo.gdal
import pandas as pd
import extract_country_data as ecd

def test_areas_reasonable():
    num = 0
    for filename in glob.glob('*.csv'):
        num = num + 1
        df = pd.read_csv(filename).set_index('Country')
        for country, row in df.iterrows():
            if country == 'Antarctica':
                continue
            area = row.sum()
            expected = expected_area[country.upper()]
            margin = max(expected * 0.20, 1000)
            assert area > (expected - margin)
            assert area < (expected + margin)
    assert num >= 4

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
    lookupobj = ecd.LClookup()
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
    "GUINEA-BISSAU": 36125,
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
    "LIBERIA": 111369,
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
    "MOROCCO": 590000,  # 446550,  disputed territory
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
    "NORWAY": 323802,
    "OMAN": 309500,
    "PAKISTAN": 796095,
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
    "UNITED ARAB EMIRATES": 83600,
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
    "WESTERN SAHARA": 90000,  # 266000, disputed territory
    "YEMEN": 527968,
    "ZAMBIA": 752618,
    "ZIMBABWE": 390757,
    }
