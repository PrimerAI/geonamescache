import osm_names
from utils import ResolutionTypes, standardize_loc_name


class DataSource(object):

    """
    Allows search for locations by name or id. Search will be case-insensitive for strings
    with more than three non-punctuation characters, and case-sensitive otherwise.
        
    Returns results of the form

    {
        id: {
            id: int,                    # Globally unique ID
            resolution: str,            # One of ResolutionTypes.{CITY, ADMIN_1, ADMIN_2, COUNTRY}
            name: str,                  # Main name
            country: str,               # Country name
            country_code: str,          # 2 letter country code
            country_id: int,            # Country ID 
            admin_level_1: Optional[str],       # Admin 1 name (only if this is a city or admin_2)
            admin_level_1_id: Optional[int],    # Admin 1 ID (only if this is a city or admin_2)
            admin_level_2: Optional[str],       # Admin 2 name (only if this is a city)
            admin_level_2_id: Optional[int],    # Admin 2 ID (only if this is a city)
            importance: float,                  # Importance score for a location, based upon
                                                # the number of wiki links to the location.
                                                # The scale is [0 - 1].
            latitude: Optional[float],          # Latitude
            longitude: Optional[float],         # Longitude
        }
    }
    
    Location resolutions go from most specific to least specific as
    
        CITY
        ADMIN_LEVEL_2
        ADMIN_LEVEL_1
        COUNTRY
    
    where more specific resolutions may belong inside less specific resolutions.
    For example, there is the location
    
        Austin
        Travis County
        Texas
        United States
        
    """

    CONTINENTS = {
        u'Antarctica', u'North America', u'South America', u'Central America', u'Oceania',
        u'Africa', u'Asia', u'Europe', u'Middle East'
    }
    OCEANS = {u'Atlantic', u'Pacific', u'Indian', u'Southern', u'Arctic'}

    def __init__(self):
        self._locations_by_name, self._locations_by_id = osm_names.load_data()

    def _name_search(self, name, resolution=None):
        name = standardize_loc_name(name)
        if name in DataSource.CONTINENTS or name in DataSource.OCEANS:
            return {}
        return {
            id_: loc.copy() for id_, loc in self._locations_by_name[name].iteritems()
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
