import csv
import json
import os
from collections import defaultdict

from manual_alternate_names import FIXED_ALTERNATE_NAMES
from utils import (
    get_alt_punc_names,
    ResolutionTypes,
    standardize_loc_name,
)


_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
_DATA_FILES = {
    'country': os.path.join(_data_dir, 'countryInfo.txt'),
    'admin_1': os.path.join(_data_dir, 'admin1Codes.txt'),
    'admin_2': os.path.join(_data_dir, 'admin2Codes.txt'),
    'city': os.path.join(_data_dir, 'cities5000.txt'),
    'alt_wiki_names': os.path.join(_data_dir, 'alt_wiki_names.json'),
    'estimated_importance': os.path.join(_data_dir, 'estimated_importance.json'),
}

# We want to keep only meaningful types of locations from the data set. See
# http://www.geonames.org/export/codes.html for what each feature code means.
_KEEP_FEATURE_CODES = {
    'PPL', 'PPLA', 'PPLA2', 'PPLA3', 'PPLA4', 'PPLC', 'PPLF', 'PPLG', 'PPLL', 'PPLR', 'PPLS', 'PPLX'
}

_MIN_POPULATION_FOR_ALT_WIKI_NAMES = 10 ** 5

_LOCATIONS_BY_NAME = defaultdict(dict)
_LOCATIONS_BY_ID = {}

def load_data():
    """
    Reads in data from geonames, as well as our own computed alternative names from wikipedia and
    estimated importance scores based off of OSM data.
    
    Returns two dictionaries with data of the format described in data_source.py.
    """
    if _LOCATIONS_BY_ID:
        return _LOCATIONS_BY_NAME, _LOCATIONS_BY_ID

    # We need to read the locations in order of country -> admin level 1 -> admin level 2 -> city.
    # This is so that the higher resolution locations can look up the lower resolution locations
    # that they belong to, and compute the necessary fields.
    countries_by_code = _load_country_data(_DATA_FILES['country'])
    admin1_by_code = _load_admin1_data(_DATA_FILES['admin_1'], countries_by_code)
    admin2_by_code = _load_admin2_data(_DATA_FILES['admin_2'], countries_by_code, admin1_by_code)
    _load_city_data(_DATA_FILES['city'], countries_by_code, admin1_by_code, admin2_by_code)
    _add_alternate_names(_DATA_FILES['alt_wiki_names'])
    _add_estimated_importances(_DATA_FILES['estimated_importance'])

    return _LOCATIONS_BY_NAME, _LOCATIONS_BY_ID

def _load_country_data(filepath):
    countries_by_code = {}

    with open(filepath) as country_file:
        reader = csv.reader(country_file, dialect='excel-tab', quoting=csv.QUOTE_NONE)
        for (
            iso, iso3, isonumeric, fips, name, capital, areakm2, population, continent_code, tld,
            currency_code, currency_name, phone, postal_code_format, postal_code_regex, languages,
            geoname_id, neighbors, equivalent_fips_code
        ) in reader:
            geoname_id = int(geoname_id)
            standard_name = standardize_loc_name(name)
            if not geoname_id or not standard_name:
                continue

            data = {
                'id': geoname_id,
                'resolution': ResolutionTypes.COUNTRY,
                'name': standard_name,
                'country_code': iso,
                'country': standard_name,
                'country_id': geoname_id,
                'population': int(population),
                'neighbor_country_codes': neighbors.split(','),
            }

            _LOCATIONS_BY_NAME[standard_name][geoname_id] = data
            for alt_name in set(get_alt_punc_names(standard_name)):
                _LOCATIONS_BY_NAME[alt_name][geoname_id] = data

            assert geoname_id not in _LOCATIONS_BY_ID
            _LOCATIONS_BY_ID[geoname_id] = data
            countries_by_code[iso] = data

    for country in _LOCATIONS_BY_ID.itervalues():
        country['neighbor_country_ids'] = [
            countries_by_code[code]['country_id'] for code in country['neighbor_country_codes']
            if code in countries_by_code
        ]
        del country['neighbor_country_codes']

    return countries_by_code

def _load_admin1_data(filepath, countries_by_code):
    admin1_by_code = {}

    with open(filepath) as admin1_file:
        reader = csv.reader(admin1_file, dialect='excel-tab', quoting=csv.QUOTE_NONE)
        for (full_admin1_code, name, ascii_name, geoname_id) in reader:
            geoname_id = int(geoname_id)
            standard_name = standardize_loc_name(name)
            if not geoname_id or not standard_name:
                continue

            country_code, admin1_code = full_admin1_code.split('.')
            country = countries_by_code[country_code]
            data = {
                'id': geoname_id,
                'resolution': ResolutionTypes.ADMIN_1,
                'name': standard_name,
                'country_code': country_code,
                'country': country['name'],
                'country_id': country['id'],
                'population': 0,
            }

            _LOCATIONS_BY_NAME[standard_name][geoname_id] = data
            for alt_name in set(get_alt_punc_names(standard_name)):
                _LOCATIONS_BY_NAME[alt_name][geoname_id] = data

            assert geoname_id not in _LOCATIONS_BY_ID
            _LOCATIONS_BY_ID[geoname_id] = data
            admin1_by_code[full_admin1_code] = data

            if country_code == 'US':
                # state abbreviations
                assert len(admin1_code) == 2
                _LOCATIONS_BY_NAME[standardize_loc_name(admin1_code)][geoname_id] = data
                _LOCATIONS_BY_NAME[
                    standardize_loc_name('%s.%s.' % (admin1_code[0], admin1_code[1]))
                ][geoname_id] = data

    return admin1_by_code

def _load_admin2_data(filepath, countries_by_code, admin1_by_code):
    admin2_by_code = {}

    with open(filepath) as admin2_file:
        reader = csv.reader(admin2_file, dialect='excel-tab', quoting=csv.QUOTE_NONE)
        for (full_admin2_code, name, ascii_name, geoname_id) in reader:
            geoname_id = int(geoname_id)
            standard_name = standardize_loc_name(name)
            if not geoname_id or not standard_name:
                continue

            country_code, admin1_code, admin2_code = full_admin2_code.split('.')
            admin1 = admin1_by_code.get('%s.%s' % (country_code, admin1_code))
            country = countries_by_code[country_code]
            data = {
                'id': geoname_id,
                'resolution': ResolutionTypes.ADMIN_2,
                'name': standard_name,
                'country_code': country_code,
                'country': country['name'],
                'country_id': country['id'],
                'admin_level_1': admin1['name'] if admin1 else '',
                'admin_level_1_id': admin1['id'] if admin1 else 0,
                'population': 0,
            }

            _LOCATIONS_BY_NAME[standard_name][geoname_id] = data
            for alt_name in set(get_alt_punc_names(standard_name)):
                _LOCATIONS_BY_NAME[alt_name][geoname_id] = data

            assert geoname_id not in _LOCATIONS_BY_ID
            _LOCATIONS_BY_ID[geoname_id] = data
            admin2_by_code[full_admin2_code] = data

    return admin2_by_code

def _load_city_data(filepath, countries_by_code, admin1_by_code, admin2_by_code):
    with open(filepath) as city_file:
        reader = csv.reader(city_file, dialect='excel-tab', quoting=csv.QUOTE_NONE)
        for (
            geoname_id, name, ascii_name, alternate_names, latitude, longitude, feature_class,
            feature_code, country_code, cc2, admin1_code, admin2_code, admin3_code, admin4_code,
            population, elevation, dem, timezone, modification_date
        ) in reader:
            if feature_code.upper() not in _KEEP_FEATURE_CODES:
                continue

            geoname_id = int(geoname_id)
            standard_name = standardize_loc_name(name)
            if not geoname_id or not standard_name:
                continue

            admin1 = admin1_by_code.get('%s.%s' % (country_code, admin1_code))
            admin2 = admin2_by_code.get('%s.%s.%s' % (country_code, admin1_code, admin2_code))
            country = countries_by_code[country_code]
            data = {
                'id': geoname_id,
                'resolution': ResolutionTypes.CITY,
                'name': standard_name,
                'country_code': country_code,
                'country': country['name'],
                'country_id': country['id'],
                'admin_level_1': admin1['name'] if admin1 else '',
                'admin_level_1_id': admin1['id'] if admin1 else 0,
                'admin_level_2': admin2['name'] if admin2 else '',
                'admin_level_2_id': admin2['id'] if admin2 else 0,
                'population': int(population),
                'latitude': float(latitude),
                'longitude': float(longitude),
            }

            _LOCATIONS_BY_NAME[standard_name][geoname_id] = data
            for alt_name in set(get_alt_punc_names(standard_name)):
                _LOCATIONS_BY_NAME[alt_name][geoname_id] = data

            assert geoname_id not in _LOCATIONS_BY_ID
            _LOCATIONS_BY_ID[geoname_id] = data

            if admin1:
                admin1['population'] += int(population)
            if admin2:
                admin2['population'] += int(population)

def _add_alternate_names(filepath):
    _add_fixed_alt_names()

    if not os.path.isfile(filepath):
        return

    with open(filepath) as alt_names_file:
        alt_names_by_id = json.load(alt_names_file)

    for id_, alt_names in alt_names_by_id.iteritems():
        location = _LOCATIONS_BY_ID[int(id_)]
        if location['population'] >= _MIN_POPULATION_FOR_ALT_WIKI_NAMES:
            for alt_name in alt_names:
                _LOCATIONS_BY_NAME[standardize_loc_name(alt_name)][int(id_)] = location

def _find_single_location(name, country, resolution):
    name = standardize_loc_name(name)
    matches = [
        loc for loc in _LOCATIONS_BY_NAME[name].itervalues()
        if (
            loc['name'] == name and
            loc['country'] == standardize_loc_name(country) and
            loc['resolution'] == resolution
        )
    ]
    assert len(matches) == 1
    return matches[0]

def _add_fixed_alt_names():
    for (real_name, country, resolution), alt_names in FIXED_ALTERNATE_NAMES.iteritems():
        location = _find_single_location(real_name, country, resolution)
        for alt_name in alt_names:
            _LOCATIONS_BY_NAME[standardize_loc_name(alt_name)][location['id']] = location

def _add_estimated_importances(filepath):
    if not os.path.isfile(filepath):
        return

    with open(filepath) as importance_file:
        estimated_importances = json.load(importance_file)

    for id_, location in _LOCATIONS_BY_ID.iteritems():
        location['estimated_importance'] = estimated_importances[str(id_)]

    washington_dc = _find_single_location(
        'Washington, D.C.', 'United States', ResolutionTypes.CITY
    )
    washington_dc['estimated_importance'] = .8

