# Geonames data

Geonames is a public data set described by http://www.geonames.org/about.html. Using the cities5000 data set, it contains ~50,000 cities, ~40,000 admin level 2 districts, ~4,000 admin level 1 districts, and ~250 countries. For each city, the data has an unique ID, name, country code, feature code (type of location), latitude / longitude, and the admin districts (levels 1 - 4) it belongs to.

## Using the data

```
from data_source import DataSource

data_source = DataSource()
print data_source.all_locations_search('Lebanon')
print data_source.get_location_by_id(6252001) # USA
```

See `data_source.py` for the format of the returned results.

## Generating the full data set from scratch

We need to take several steps to generate the full data set from Geonames (running the scripts from the root geonamescache directory):

1. Download the Geonames data

    The latest public version of the data is at http://download.geonames.org/export/dump/. At the moment, we use the premium version of the data set (supposed to be cleaner), saved in https://drive.google.com/drive/folders/0B-spomFLrCHxejVqX09fUlRCdVE. Regardless of where you get the data from, put the following files in `geonamescache/geonames/data`.
    
    - countryInfo.txt
    - admin1CodesASCII.txt
    - admin2Codes.txt
    - cities5000.txt (could use cities1000.txt instead)
    
    Note: in the premium data set both 'London' and 'City of London' appear as entries, even though they refer to the same city. We manually deleted 'City of London' in the version saved here on github.
    
2. Download OpenStreetMaps data

    The current version of the top 100K locations in TSV format is at https://github.com/OSMNames/OSMNames/releases/download/v1.1/planet-latest-100k.tsv.gz and is already saved as `geonamescache/osm_names/data/osm_data.tsv`. There isn't any indication that this file will be updated in the future, but if you get a new version replace the above file.

3. Generate estimated importances scores for the Geonames data

    Run
    
    ```
    python scripts/estimate_importances.py geonamescache/osm_names/data/osm_data.tsv geonamescache/geonames/data/estimated_importance.json
    ```
    
    Check that the reported results are consistent with those documented in the script.
    
4. Find alternate names of locations from wikipedia

    Run
    
    ```
    python scripts/lookup_alt_names_on_wiki.py geonamescache/geonames/data/alt_wiki_names.json scripts/readable_wiki_names.tsv
    ```
    
    This script will take about a day to run. Check the saved output file in the script directory to see the results.
    
5. Dump the full data set into a single JSON file

    Run
    
    ```
    python scripts/create_single_json.py geonamescache/geonames/data/geonames_all.py
    ```
    
    This loads and processes the full data set, and writes it to a file so that future uses of the code will only need to load the data from a single file.
    
6. Verify that the data is set up correctly

    Run
    
    ```
    python setup.py install
    py.test tests/test_geonames_data.py
    ```
    
## Moving code to primer_core

Our locations code is currently in primer_core. To move an updated version of the data into primer_core, move the following files from this directory into `primer_core/entities/locations/data_source/`

    data_source.py
    utils.py
    data/geonames_all.json
