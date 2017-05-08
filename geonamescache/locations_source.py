import re

from geonames import geonames
from osm_names import osm_names
from osm_names.utils import ResolutionTypes, standardize_loc_name


class LocationsSource(object):

    """
    Allows search for locations by name or id.

    Returns results of the form

    {
        id: {
            id: int,
            resolution: str,
            name: str,
            country: str,
            country_code: str,
            country_id: int,
            admin_level_1: Optional[str],
            admin1_level_1_id: Optional[int], # can be 0 if admin level 1 is not present in data set
            admin_level_2: Optional[str],
            admin_level_2_id: Optional[int], # can be 0 if admin level 2 is not present in data set
            city: Optional[str],
            importance: Optional[float],
            population: Optional[int],
            latitude: Optional[float], # can be missing for admin districts
            longitude: Optional[float], # can be missing for admin districts
            neighbor_country_ids: Optional[List[int]], # only available for countries
        }
    }
    """

    def __init__(self, source='geonames'):
        assert source in ('osm', 'geonames')
        if source == 'osm':
            self._locations_by_name, self._locations_by_id = osm_names.load_data()
        else:
            self._locations_by_name, self._locations_by_id = geonames.load_data()

    def get_continents(self):
        return (
            u'Antarctica', u'North America', u'South America', u'Central America', u'Oceania',
            u'Africa', u'Asia', u'Europe', u'Middle East'
        )

    def _name_search(self, name, resolution=None):
        name = standardize_loc_name(name)
        return dict(
            (id_, loc.copy()) for id_, loc in self._locations_by_name[name].iteritems()
            if not resolution or loc['resolution'] == resolution
        )

    def city_search(self, city_name):
        return self._name_search(city_name, ResolutionTypes.CITY)

    def admin_level_1_search(self, admin1_name):
        return self._name_search(admin1_name, ResolutionTypes.ADMIN_1)

    def admin_level_2_search(self, admin2_name):
        return self._name_search(admin2_name, ResolutionTypes.ADMIN_2)

    def country_search(self, country_name):
        return self._name_search(country_name, ResolutionTypes.COUNTRY)

    def all_locations_search(self, name):
        return self._name_search(name)

    def get_location_by_id(self, id_):
        if id_ in self._locations_by_id:
            return self._locations_by_id[id_].copy()
