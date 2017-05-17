import json
import os

from utils import ResolutionTypes, standardize_loc_name


_LOCATIONS_BY_NAME = None

def _get_locations_by_name():
    global _LOCATIONS_BY_NAME

    if _LOCATIONS_BY_NAME is None:
        data_filepath = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'data', 'geonames_all.json'
        )
        with open(data_filepath) as f:
            _LOCATIONS_BY_NAME = json.load(f)

    return _LOCATIONS_BY_NAME


class DataSource(object):

    """
    Allows search for locations by name or id.
    
    Search will be case-insensitive for strings with more than three non-punctuation characters,
    and case-sensitive otherwise. We have case-sensitive search for shorter strings because
    there are abbreviations that should only be matched when the case also matches - e.g.
    Usa, Japan and Eu, France are locations we do not want to be matched with USA or EU.
        
    Returns results of the form

    {
        id: {
            id: str,                    # Globally unique ID
            resolution: str,            # One of ResolutionTypes.{CITY, ADMIN_1, ADMIN_2, COUNTRY}
            name: str,                  # Main name
            country: str,               # Country name
            country_code: str,          # 2 letter country code
            country_id: str,            # Country ID 
            admin_level_1: Optional[str],       # Admin 1 name (only if this is a city or admin_2)
            admin_level_1_id: Optional[str],    # Admin 1 ID (only if this is a city or admin_2)
            admin_level_2: Optional[str],       # Admin 2 name (only if this is a city)
            admin_level_2_id: Optional[str],    # Admin 2 ID (only if this is a city)
            population: int,                    # Population. This is provided for cities and
                                                # countries (although it can be 0 for small
                                                # cities). This is calculated for admin districts
                                                # according to the sum of the populations of its
                                                # cities.
            estimated_importance: float,        # Estimated importance score for a location
                                                # The scale is [0 - 1].
            latitude: Optional[float],          # Only available for cities right now
            longitude: Optional[float],         # Only available for cities right now
            neighbor_country_ids: Optional[List[int]],  # IDs of neighboring countries
                                                        # Only available for countries
        }
    }
    
    The hierarchy of location resolutions goes from most specific to least specific as
    
        CITY
        ADMIN_LEVEL_2   [e.g. in the US, this corresponds to counties]
        ADMIN_LEVEL_1   [e.g. in the US, this corresponds to states]
        COUNTRY
    
    where more specific resolutions may belong inside less specific resolutions.
    For example, there is the location
    
        Austin          [CITY]
        Travis County   [ADMIN_LEVEL_2]
        Texas           [ADMIN_LEVEL_1]
        United States   [COUNTRY]
        
    """

    CONTINENTS = {
        u'Antarctica', u'North America', u'South America', u'Central America', u'Oceania',
        u'Africa', u'Asia', u'Europe', u'EU', u'Middle East'
    }
    OCEANS = {u'Atlantic', u'Pacific', u'Indian', u'Southern', u'Arctic'}

    def __init__(self):
        self._locations_by_name = _get_locations_by_name()
        self._locations_by_id = {}
        for locations_with_name in self._locations_by_name.itervalues():
            for id_, location in locations_with_name.iteritems():
                self._locations_by_id[id_] = location

    def _name_search(self, name, resolution=None):
        name = standardize_loc_name(name)
        if name in DataSource.CONTINENTS or name in DataSource.OCEANS:
            return {}
        return {
            id_: loc.copy() for id_, loc in self._locations_by_name.get(name, {}).iteritems()
            if not resolution or loc['resolution'] == resolution
        }

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

