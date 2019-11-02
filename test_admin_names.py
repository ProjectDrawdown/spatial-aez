import admin_names

def test_lookup():
    assert admin_names.lookup('Cabo Verde') == 'Cape Verde'
    assert admin_names.lookup('Scarborough Reef') is None

def test_region_mapping():
    assert 'OECD90' in admin_names.region_mapping['Belgium']
    assert 'EU' in admin_names.region_mapping['Belgium']
