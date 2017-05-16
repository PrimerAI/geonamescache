from primer_core.entities.locations.data_source.data_source import DataSource
from primer_core.entities.locations.data_source.geonames import load_data
from primer_core.entities.locations.data_source.utils import (
    get_alt_punc_names,
    ResolutionTypes,
    standardize_loc_name,
)


def test_data_source():
    data_source = DataSource()

    # continent
    assert not data_source.all_locations_search('Africa')

    # city
    san_franciscos = data_source.city_search('san francisco')
    assert len(san_franciscos) > 1
    assert any(
        loc['admin_level_1'] == 'California' and loc['country'] == 'United States'
        for loc in san_franciscos.itervalues()
    )
    assert all(loc['resolution'] == ResolutionTypes.CITY for loc in san_franciscos.itervalues())

    # admin level 1
    washingtons = data_source.admin_level_1_search('washington')
    assert len(washingtons) > 1
    assert any(loc['name'] == 'Washington, D.C.' for loc in washingtons.itervalues())
    assert all(loc['resolution'] == ResolutionTypes.ADMIN_1 for loc in washingtons.itervalues())
    # admin level 2
    jackson_counties = data_source.admin_level_2_search('jackson county')
    assert len(jackson_counties) > 1
    assert all(
        loc['resolution'] == ResolutionTypes.ADMIN_2 for loc in jackson_counties.itervalues()
    )

    # country
    japans = data_source.country_search('japan')
    assert len(japans) == 1
    assert japans.values()[0]['resolution'] == ResolutionTypes.COUNTRY

    # all locations
    lebanons = data_source.all_locations_search('lebanon')
    assert len(lebanons) > 1
    assert any(loc['resolution'] == ResolutionTypes.COUNTRY for loc in lebanons.itervalues())
    assert any(loc['resolution'] == ResolutionTypes.CITY for loc in lebanons.itervalues())

    # missing location
    locations = data_source.all_locations_search('bad location')
    assert not locations

    # by ID
    japan = data_source.get_location_by_id(japans.values()[0]['id'])
    assert japan
    assert japan['resolution'] == ResolutionTypes.COUNTRY

def test_data_format():
    locations_by_name, locations_by_id = load_data()

    for location in locations_by_id.itervalues():
        _test_mandatory_fields(location, locations_by_id)

        if location['resolution'] == ResolutionTypes.COUNTRY:
            _test_country_fields(location)
        elif location['resolution'] == ResolutionTypes.ADMIN_2:
            _test_admin_2_fields(location, locations_by_id)
        elif location['resolution'] == ResolutionTypes.CITY:
            _test_city_fields(location, locations_by_id)

def _test_mandatory_fields(location, locations_by_id):
    # id
    assert isinstance(location['id'], int)
    assert location['id'] > 0
    # resolution
    assert location['resolution'] in (
        ResolutionTypes.CITY, ResolutionTypes.ADMIN_1, ResolutionTypes.ADMIN_2,
        ResolutionTypes.COUNTRY
    )
    # name
    assert location['name'] == standardize_loc_name(location['name'])
    # country
    assert isinstance(location['country'], str)
    # country_code
    assert len(location['country_code']) == 2
    assert location['country_code'].isupper()
    # country_id
    country = locations_by_id[location['country_id']]
    assert country
    assert country['name'] == location['country']
    # population
    assert isinstance(location['population'], int)
    assert location['population'] >= 0
    # estimated importance
    assert isinstance(location['estimated_importance'], float)
    assert 0 < location['estimated_importance'] < 1

def _test_country_fields(country):
    # neighbor_country_ids
    assert isinstance(country['neighbor_country_ids'], list)

def _test_admin_2_fields(admin_2, locations_by_id):
    # admin_level_1
    assert isinstance(admin_2['admin_level_1'], str)
    # admin_level_1_id
    admin_1 = locations_by_id[admin_2['admin_level_1_id']]
    assert admin_1
    assert admin_1['name'] == admin_2['admin_level_1']

def _test_city_fields(city, locations_by_id):
    # admin_level_1
    assert isinstance(city['admin_level_1'], str)
    # admin_level_1_id
    if city['admin_level_1_id'] != 0:
        admin_1 = locations_by_id[city['admin_level_1_id']]
        assert admin_1
        assert admin_1['name'] == city['admin_level_1']
    # admin_level_2
    assert isinstance(city['admin_level_2'], str)
    # admin_level_2_id
    if city['admin_level_2_id'] != 0:
        admin_2 = locations_by_id[city['admin_level_2_id']]
        assert admin_2
        assert admin_2['name'] == city['admin_level_2']
    # latitude
    assert isinstance(city['latitude'], float)
    # longitude
    assert isinstance(city['longitude'], float)

def test_geonames_data():
    locations_by_name, locations_by_id = load_data()

    _test_populations(locations_by_id)
    _test_basic_alternate_names(locations_by_name)
    _test_basic_estimated_importances(locations_by_name, locations_by_id)

def _test_populations(locations_by_id):
    n_big_locations = len(
        [loc for loc in locations_by_id.itervalues() if loc['population'] > 10 ** 6]
    )
    assert n_big_locations > 1000
    n_medium_locations = len(
        [loc for loc in locations_by_id.itervalues() if 10 ** 6 > loc['population'] > 10 ** 4]
    )
    assert n_medium_locations > 30000

    for location in locations_by_id.itervalues():
        if location['resolution'] == ResolutionTypes.ADMIN_1:
            _check_subpopulation(locations_by_id, location, ('country_id',))
        elif location['resolution'] == ResolutionTypes.ADMIN_2:
            _check_subpopulation(locations_by_id, location, ('admin_level_1_id',))
        elif location['resolution'] == ResolutionTypes.CITY:
            _check_subpopulation(
                locations_by_id, location, ('country_id', 'admin_level_1_id', 'admin_level_2_id')
            )

def _check_subpopulation(locations_by_id, sublocation, parent_id_fields):
    for parent_id_field in parent_id_fields:
        if sublocation[parent_id_field] != 0:
            parent = locations_by_id[sublocation[parent_id_field]]
            if parent['resolution'] == ResolutionTypes.COUNTRY:
                # we do not compute country populations - for very small countries, sometimes
                # the population is a bit less than its sublocations.
                assert 2 * parent['population'] >= sublocation['population']
            else:
                assert parent['population'] >= sublocation['population']

def _test_basic_alternate_names(locations_by_name):
    for name, alt_names, country, resolution in (
        # hardcoded alternate names
        (
            'United States',
            (
                'US', 'U.S.', 'USA', 'U.S.A.', 'the United States', 'United States of America',
                'America'
            ),
            'United States',
            ResolutionTypes.COUNTRY,
        ),
        (
            'United Kingdom',
            ('Great Britain', 'Britain', 'UK', 'U.K.'),
            'United Kingdom',
            ResolutionTypes.COUNTRY,
        ),
        (
            'Washington, D.C.',
            ('Washington', 'DC', 'D.C.', 'District of Columbia',),
            'United States',
            ResolutionTypes.CITY,
        ),
        # alternative punctuation names
        ('Saint Lucia', ('St. Lucia',), 'Saint Lucia', ResolutionTypes.COUNTRY),
        ('Seongnam-Si', ('Seongnam Si',), 'South Korea', ResolutionTypes.CITY),
        # alternative wiki names
        ('Russia', ('Russian Federation',), 'Russia', ResolutionTypes.COUNTRY),
        ('Thailand', ('Siam',), 'Thailand', ResolutionTypes.COUNTRY),
        ('Beijing', ('Peking',), 'China', ResolutionTypes.CITY),
        ('Vienna', ('Wien',), 'Austria', ResolutionTypes.CITY),
        ('Philadelphia', ('Philly',), 'United States', ResolutionTypes.CITY),
    ):
        for alt_name in alt_names:
            matching_locations = [
                loc for loc in locations_by_name[standardize_loc_name(alt_name)].itervalues()
                if (
                    loc['name'] == name and
                    loc['country'] == country and
                    loc['resolution'] == resolution
                )
            ]
            assert len(matching_locations) == 1, '%s was not found as an alternate name for %s' % (
                alt_name, name
            )

def _test_basic_estimated_importances(locations_by_name, location_by_id):
    # check distribution of estimated importances
    all_importances = [loc['estimated_importance'] for loc in location_by_id.itervalues()]
    all_importances.sort()
    n_locations = len(all_importances)
    assert all_importances[0] == .4
    assert all_importances[int(.25 * n_locations)] < .45
    assert all_importances[int(.5 * n_locations)] < .5
    assert all_importances[int(.75 * n_locations)] < .55
    assert all_importances[int(.9 * n_locations)] < .55
    assert all_importances[int(.98 * n_locations)] < .6
    assert all_importances[-1] > .9

    # check estimated importances of some key locations
    for name, country, resolution, min_importance in (
        ('United States', 'United States', ResolutionTypes.COUNTRY, .9),
        ('Germany', 'Germany', ResolutionTypes.COUNTRY, .9),
        ('Russia', 'Russia', ResolutionTypes.COUNTRY, .9),
        ('Japan', 'Japan', ResolutionTypes.COUNTRY, .9),
        ('Australia', 'Australia', ResolutionTypes.COUNTRY, .8),
        ('Mexico', 'Mexico', ResolutionTypes.COUNTRY, .8),
        ('Egypt', 'Egypt', ResolutionTypes.COUNTRY, .8),
        ('Singapore', 'Singapore', ResolutionTypes.COUNTRY, .7),
        ('New York City', 'United States', ResolutionTypes.CITY, .7),
        ('London', 'United Kingdom', ResolutionTypes.CITY, .7),
        ('Rome', 'Italy', ResolutionTypes.CITY, .7),
        ('Washington, D.C.', 'United States', ResolutionTypes.CITY, .7),
        ('Tokyo', 'Japan', ResolutionTypes.CITY, .6),
        ('Los Angeles', 'United States', ResolutionTypes.CITY, .6),
        ('New Jersey', 'United States', ResolutionTypes.ADMIN_1, .6),
    ):
        matching_locations = [
            loc for loc in locations_by_name[standardize_loc_name(name)].itervalues()
            if (
                loc['name'] == name and
                loc['country'] == country and
                loc['resolution'] == resolution
            )
        ]
        if len(matching_locations) != 1:
            print name, country, resolution, len(matching_locations)
        assert len(matching_locations) == 1
        assert matching_locations[0]['estimated_importance'] > min_importance, (
            '%s does not have an importance score of at least %f' % (name, min_importance)
        )

def test_standardize_name():
    # check output type
    assert isinstance(standardize_loc_name('US'), str)
    assert isinstance(standardize_loc_name(u'S\xe3o Paulo'), str)

    # check short names
    assert standardize_loc_name('US') == 'US'
    assert standardize_loc_name('USA') == 'USA'
    assert standardize_loc_name('U.S.A.') == 'U.S.A.'
    assert standardize_loc_name('usa') == 'usa'

    # check long names
    assert standardize_loc_name('Washington, d.c.') == 'Washington, D.C.'
    assert standardize_loc_name('japan') == 'Japan'
    assert standardize_loc_name(u'S\xe3o pauLo') == 'Sao Paulo'
    assert standardize_loc_name(u'Legan\xe9s') == 'Leganes'

def test_alt_punc_names():
    assert 'NaMan' in get_alt_punc_names("Na'Man")
    assert 'Ust Abakan' in get_alt_punc_names('Ust-Abakan')
    assert 'St. Louis' in get_alt_punc_names('St Louis')
    assert 'St. Petersburg' in get_alt_punc_names('Saint Petersburg')
    assert 'Netherlands' in get_alt_punc_names('The Netherlands')
    assert 'New York' in get_alt_punc_names('City of New York')
    assert 'Hey' in get_alt_punc_names('Hey (there)')
    assert 'Hey' in get_alt_punc_names('Hey, there')

