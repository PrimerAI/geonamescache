from utils import ResolutionTypes


# Map of (name, country, resolution) to list of alternate names, that we want to make sure
# is in our data set.
FIXED_ALTERNATE_NAMES = {
    # Countries
    ('United States', 'United States', ResolutionTypes.COUNTRY): (
        'USA', 'U.S.A.', 'US', 'U.S.', 'the United States', 'United States of America',
        'America'
    ),
    ('United Kingdom', 'United Kingdom', ResolutionTypes.COUNTRY): (
        'Great Britain', 'Britain', 'UK', 'U.K.'
    ),
    ('Palestinian Territory', 'Palestinian Territory', ResolutionTypes.COUNTRY): (
        'Palestine', 'State of Palestine'
    ),
    ('South Korea', 'South Korea', ResolutionTypes.COUNTRY): ('Korea',),
    ('North Korea', 'North Korea', ResolutionTypes.COUNTRY): ('Korea',),
    ('Netherlands', 'Netherlands', ResolutionTypes.COUNTRY): ('The Netherlands', 'Holland'),
    ('Ivory Coast', 'Ivory Coast', ResolutionTypes.COUNTRY): ("Cote d'Ivoire",),
    # Admin level 1's
    ('Washington', 'United States', ResolutionTypes.ADMIN_1): ('Washington State',),
    ('New York', 'United States', ResolutionTypes.ADMIN_1): ('NY', 'N.Y.'),
    # Cities
    ('Washington, D.C.', 'United States', ResolutionTypes.CITY): (
        'District of Columbia', 'Washington', 'DC', 'D.C.', 'Washington, DC', 'Washington D.C.',
        'Washington DC'
    ),
    ('New York City', 'United States', ResolutionTypes.CITY): ('NYC', 'N.Y.C.'),
    ('Venice', 'Italy', ResolutionTypes.CITY): ('Venezia',),
    ('Los Angeles', 'United States', ResolutionTypes.CITY): ('LA', 'L.A.'),
}
