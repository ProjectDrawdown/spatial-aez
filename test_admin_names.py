import admin_names

def test_lookup():
    assert admin_names.lookup('Cabo Verde') == 'Cape Verde'
    assert admin_names.lookup('Scarborough Reef') is None
