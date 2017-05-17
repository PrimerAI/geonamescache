import json
import sys
from geonamescache.geonames.geonames import load_data


def run(output_filepath):
    locations_by_name, locations_by_id = load_data()
    with open(output_filepath, 'w') as output:
        json.dump(locations_by_name, output)


if __name__ == '__main__':
    run(sys.argv[1])
