import csv
import json
import os
from collections import defaultdict

from utils import (
    get_alt_punc_names,
    ResolutionTypes,
    standardize_loc_name,
)


data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
_DATA_FILES = {
    'country': os.path.join(data_dir, 'countryInfo.txt'),
    'admin_1': os.path.join(data_dir, 'admin1Codes.txt'),
    'admin_2': os.path.join(data_dir, 'admin2Codes.txt'),
    'city': os.path.join(data_dir, 'cities5000.txt'),
    'alt_wiki_names': os.path.join(data_dir, 'alt_wiki_names.json'),
}

_KEEP_FEATURE_CODES = {
    'PPL', 'PPLA', 'PPLA2', 'PPLA3', 'PPLA4', 'PPLC', 'PPLF', 'PPLG', 'PPLL', 'PPLR', 'PPLS', 'PPLX'
}

_MIN_POPULATION_FOR_ALT_WIKI_NAMES = 10 ** 5

def load_data():
    locations_by_name = defaultdict(dict)
    locations_by_id = {}

    countries_by_code = _load_country_data(
        _DATA_FILES['country'], locations_by_name, locations_by_id
    )
    admin1_by_code = _load_admin1_data(
        _DATA_FILES['admin_1'], locations_by_name, locations_by_id, countries_by_code
    )
    admin2_by_code = _load_admin2_data(
        _DATA_FILES['admin_2'], locations_by_name, locations_by_id, countries_by_code,
        admin1_by_code
    )
    _load_city_data(
        _DATA_FILES['city'], locations_by_name, locations_by_id, countries_by_code,
        admin1_by_code, admin2_by_code
    )
    _add_alternate_names(
        _DATA_FILES['alt_wiki_names'], locations_by_name, locations_by_id
    )

    del locations_by_name['']

    return locations_by_name, locations_by_id

def _load_country_data(filepath, locations_by_name, locations_by_id):
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
            data = dict(
                id=geoname_id,
                resolution=ResolutionTypes.COUNTRY,
                name=standard_name,
                country_code=iso,
                country=standard_name,
                country_id=geoname_id,
                population=int(population),
                neighbor_country_codes=neighbors.split(','),
            )

            for name in set(
                standardize_loc_name(alt_name) for alt_name in
                [standard_name] + get_alt_punc_names(standard_name)
            ):
                locations_by_name[name][geoname_id] = data
            assert geoname_id not in locations_by_id
            locations_by_id[geoname_id] = data
            countries_by_code[iso] = data

    for country in locations_by_id.itervalues():
        if country['resolution'] != ResolutionTypes.COUNTRY:
            continue
        neighbor_country_codes = country['neighbor_country_codes']
        del country['neighbor_country_codes']
        country['neighbor_country_ids'] = [
            countries_by_code[code]['country_id'] for code in neighbor_country_codes
            if code in countries_by_code
        ]

    return countries_by_code

def _load_admin1_data(filepath, locations_by_name, locations_by_id, countries_by_code):
    admin1_by_code = {}

    with open(filepath) as admin1_file:
        reader = csv.reader(admin1_file, dialect='excel-tab', quoting=csv.QUOTE_NONE)
        for (full_admin1_code, name, ascii_name, geoname_id) in reader:
            geoname_id = int(geoname_id)
            standard_name = standardize_loc_name(name)
            country_code, admin1_code = full_admin1_code.split('.')
            country = countries_by_code[country_code]
            data = dict(
                id=geoname_id,
                resolution=ResolutionTypes.ADMIN_1,
                name=standard_name,
                admin_level_1=standard_name,
                country_code=country_code,
                country=country['name'],
                country_id=country['id'],
                population=0,
            )

            for name in set(
                standardize_loc_name(alt_name) for alt_name in
                [standard_name] + get_alt_punc_names(standard_name)
            ):
                locations_by_name[name][geoname_id] = data
            assert geoname_id not in locations_by_id
            locations_by_id[geoname_id] = data
            admin1_by_code[full_admin1_code] = data

            if country_code == 'US':
                # state abbreviations
                assert len(admin1_code) == 2
                locations_by_name[standardize_loc_name(admin1_code)][geoname_id] = data
                locations_by_name[
                    standardize_loc_name('%s.%s.' % (admin1_code[0], admin1_code[1]))
                ][geoname_id] = data

    return admin1_by_code

def _load_admin2_data(
    filepath, locations_by_name, locations_by_id, countries_by_code, admin1_by_code
):
    admin2_by_code = {}

    with open(filepath) as admin2_file:
        reader = csv.reader(admin2_file, dialect='excel-tab', quoting=csv.QUOTE_NONE)
        for (full_admin2_code, name, ascii_name, geoname_id) in reader:
            geoname_id = int(geoname_id)
            standard_name = standardize_loc_name(name)
            country_code, admin1_code, admin2_code = full_admin2_code.split('.')
            admin1 = admin1_by_code.get('%s.%s' % (country_code, admin1_code))
            country = countries_by_code[country_code]
            data = dict(
                id=geoname_id,
                resolution=ResolutionTypes.ADMIN_2,
                name=standard_name,
                admin_level_1=admin1['name'] if admin1 else '',
                admin_level_1_id=admin1['id'] if admin1 else 0,
                admin_level_2=standard_name,
                country_code=country_code,
                country=country['name'],
                country_id=country['id'],
                population=0,
            )

            for name in set(
                standardize_loc_name(alt_name) for alt_name in
                [standard_name] + get_alt_punc_names(standard_name)
            ):
                locations_by_name[name][geoname_id] = data
            assert geoname_id not in locations_by_id
            locations_by_id[geoname_id] = data
            admin2_by_code[full_admin2_code] = data

    return admin2_by_code

def _load_city_data(
    filepath, locations_by_name, locations_by_id, countries_by_code, admin1_by_code, admin2_by_code
):
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
            admin1 = admin1_by_code.get('%s.%s' % (country_code, admin1_code))
            admin2 = admin2_by_code.get('.'.join((country_code, admin1_code, admin2_code)))
            country = countries_by_code[country_code]
            data = dict(
                id=geoname_id,
                resolution=ResolutionTypes.CITY,
                name=standard_name,
                latitude=float(latitude),
                longitude=float(longitude),
                country_code=country_code,
                city=standard_name,
                admin_level_1=admin1['name'] if admin1 else '',
                admin_level_1_id=admin1['id'] if admin1 else 0,
                admin_level_2=admin2['name'] if admin2 else '',
                admin_level_2_id=admin2['id'] if admin2 else 0,
                country=country['name'],
                country_id=country['id'],
                population=int(population),
            )

            for name in set(
                standardize_loc_name(alt_name) for alt_name in
                [standard_name] + get_alt_punc_names(standard_name)
            ):
                locations_by_name[name][geoname_id] = data
            assert geoname_id not in locations_by_id
            locations_by_id[geoname_id] = data

            if admin1:
                admin1['population'] += int(population)
            if admin2:
                admin2['population'] += int(population)

def _add_alternate_names(filepath, locations_by_name, locations_by_id):
    _add_fixed_alt_names(locations_by_name)

    if not os.path.isfile(filepath):
        return

    with open(filepath) as alt_names_file:
        alt_names_by_id = json.load(alt_names_file)

    for id_, alt_names in alt_names_by_id.iteritems():
        location = locations_by_id[int(id_)]
        if location['population'] >= _MIN_POPULATION_FOR_ALT_WIKI_NAMES:
            for alt_name in alt_names:
                locations_by_name[alt_name][int(id_)] = location

def _add_fixed_alt_names(locations_by_name):
    for real_name, alt_names, country, resolution in (
        # Countries
        (
            'United States',
            ('USA', 'U.S.A.', 'US', 'U.S.', 'the United States', 'United States of America'),
            'United States',
            ResolutionTypes.COUNTRY
        ),
        (
            'United Kingdom',
            ('Great Britain', 'Britain', 'UK', 'U.K.'),
            'United Kingdom',
            ResolutionTypes.COUNTRY
        ),
        ('South Korea', ('Korea',), 'South Korea', ResolutionTypes.COUNTRY),
        ('North Korea', ('Korea',), 'North Korea', ResolutionTypes.COUNTRY),
        ('Netherlands', ('The Netherlands', 'Holland',), 'Netherlands', ResolutionTypes.COUNTRY),
        ('Ivory Coast', ("Cote d'Ivoire",), 'Ivory Coast', ResolutionTypes.COUNTRY),
        # Admin level 1's
        ('Washington', ('Washington State',), 'United States', ResolutionTypes.ADMIN_1),
        ('California', ('Calif.',), 'United States', ResolutionTypes.ADMIN_1),
        # Cities
        ('New York City', ('NYC', 'N.Y.C.'), 'United States', ResolutionTypes.CITY),
        ('Venice', ('Venezia',), 'Italy', ResolutionTypes.CITY),
    ):
        locations = [
            loc for loc in locations_by_name[standardize_loc_name(real_name)].itervalues()
            if (
                loc['name'] == real_name and
                loc['country'] == country and
                loc['resolution'] == resolution
            )
        ]
        assert len(locations) == 1
        location = locations[0]

        for alt_name in alt_names:
            locations_by_name[standardize_loc_name(alt_name)][location['id']] = location
