import re
import string
from unidecode import unidecode


class ResolutionTypes(object):

    COUNTRY = 'COUNTRY'
    ADMIN_1 = 'ADMIN_LEVEL_1'
    ADMIN_2 = 'ADMIN_LEVEL_2'
    CITY = 'CITY'

punctuation_chars = set(string.punctuation)
def standardize_loc_name(name):
    """
    Returns a standard form unicode string for a location name. For names with more than
    three non-punctuation characters, this will be in title-case. For names with three or
    fewer such characters, the case will be as-is (since for abbreviations we should
    require matches to have the cases match).
    
    All location names stored in the data set and all search strings for location names
    should be of this form in order to match correctly.
    """
    if name is None:
        return None

    if not isinstance(name, unicode):
        name = unicode(name, 'utf-8')
    name = unidecode(name)
    num_letters = len([char for char in name if char not in punctuation_chars])
    if num_letters > 3:
        name = name.title()
    return name

def get_alt_punc_names(name):
    """
    Returns a list of names (possibly repeated) of the various forms an input name could
    take on.
    """
    return [
        name.replace("'", ""),
        name.replace("-", " "),
        re.sub(r'^St ', 'St. ', name, flags=re.IGNORECASE),
        re.sub(r'^Saint ', 'St. ', name, flags=re.IGNORECASE),
        re.sub(r'^The ', '', name, flags=re.IGNORECASE),
        re.sub(r'^City of ', '', name, flags=re.IGNORECASE),
        name.split('(')[0].strip(),
        name.split(',')[0].strip(),
    ]
