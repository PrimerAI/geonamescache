import csv
import json
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import numpy as np
import pdb
import sys
import traceback

from argparse import ArgumentParser
from collections import defaultdict
from sklearn.base import clone
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import train_test_split

import geonamescache.geonames.geonames as geonames
from geonamescache.geonames.utils import (
    get_alt_punc_names,
    ResolutionTypes,
    standardize_loc_name,
)

"""
This script tries to learn a simple method to estimate location importance scores from
OpenStreetMap data using location features of Geonames data. This should give every location in
Geonames a reasonable importance score that is a proxy for how likely each location would appear
in text.

The steps:

1. Read in an OSM data file (e.g. https://github.com/OSMNames/OSMNames/releases/tag/v1.1)
2. Try to match up the Geonames locations with the OSM locations (this is difficult).
3. Setup a machine learning problem for each resolution type, to predict the OSM importances
   using the following features.
        
        country_importance:     Importance of the location's country. Note that we can generally
                                match countries between the two data sets, so know what each
                                country's importance score should be.
        population_fraction:    The ratio of the location's population to the country's population.
        
4. Train a model to learn this relationship.
5. Record a prediction for all Geonames locations (whether it was part of the training data set
   or not).

My latest run of this script yields the following results:

                Training size       Training R2         Test R2     Predicted location importances

CITY            10189               .693                .667        36838
ADMIN_LEVEL_1   1036                .721                .650        2021
ADMIN_LEVEL_2   684                 .395                .358        11710

The above numbers omit locations under MIN_POPULATION_THRESHOLD population.
COUNTRY - 241 with found OSM importances, 9 with default importances.

Notes:

I also tried using features (for cities) such as

    city population
    city population / avg city population in the country
    admin level 1 population / country population
    city population / admin level 1 population

but these were not useful.

Also, because we are most concerned with the important locations, I weight the training points
during training / evaluation according to [importance - .4] (where .4 is the lowest, baseline
importance score).
"""

MIN_POPULATION_THRESHOLD = 5 * 10 ** 3

MODELS_TYPES = {
    ResolutionTypes.CITY: GradientBoostingRegressor(
        learning_rate=.4, n_estimators=12, max_depth=3
    ),
    ResolutionTypes.ADMIN_1: GradientBoostingRegressor(
        learning_rate=.4, n_estimators=12, max_depth=2
    ),
    ResolutionTypes.ADMIN_2: Ridge(alpha=80.),
}

DEFAULT_IMPORTANCE = {
    ResolutionTypes.CITY: .4,
    ResolutionTypes.ADMIN_1: .4,
    ResolutionTypes.ADMIN_2: .4,
    ResolutionTypes.COUNTRY: .6,
}


def run(osm_data_filepath, out_filepath, show_plot):
    geo_locations_by_name, geo_locations_by_id = geonames.load_data()
    location_importances = find_osm_importances(
        osm_data_filepath, geo_locations_by_name, geo_locations_by_id
    )
    training_sets, predict_sets = get_data_sets(geo_locations_by_id, location_importances)
    models = train_models(training_sets, geo_locations_by_id, location_importances, show_plot)
    predictions = make_predictions(
        models, training_sets, predict_sets, geo_locations_by_id, location_importances
    )

    with open(out_filepath, 'w') as out:
        json.dump(predictions, out)

    if show_plot:
        plt.show()

def read_osm_locations(osm_data_filepath):
    """
    Returns a dictionary of deduplicated locations of the form
    
    {
        name: [{
            resolution:
            name:
            importance:
            country:
            etc...
        }]
    }
    """
    locations_by_name = defaultdict(list)
    # OSM names is missing some countries. Keep track of the country names and most important
    # cities (for estimating country importance).
    countries = {} # country code to name, city importance
    found_countries = {} # country code to country data
    resolution_counts = defaultdict(int)
    print '##########################'
    print 'Reading OSM data'

    with open(osm_data_filepath) as data_file:
        csv_reader = csv.reader(data_file, delimiter='\t')
        keys = next(csv_reader)
        last_importance = 1.

        for row in csv_reader:
            assert len(row) == 23
            loc_info = dict(zip(keys, row))
            importance = float(loc_info['importance'])
            assert importance <= last_importance
            last_importance = importance

            resolution = _get_resolution(loc_info)
            if not resolution:
                continue

            country_code = loc_info['country_code'].upper()
            data = dict(
                resolution=resolution,
                name=standardize_loc_name(loc_info['name']),
                importance=importance,
                city=standardize_loc_name(loc_info['city']),
                admin_level_2=standardize_loc_name(loc_info['county']),
                admin_level_1=standardize_loc_name(loc_info['state']),
                country=standardize_loc_name(loc_info['country']),
                country_code=country_code,
            )

            if _should_skip_location(data, locations_by_name):
                continue

            resolution_counts[resolution] += 1

            alt_osm_names = [
                name for name in loc_info['alternative_names'].split(',') if _is_ascii(name)
            ]
            alt_punc_name = get_alt_punc_names(data['name'])

            all_names = set(
                standardize_loc_name(name)
                for name in [data['name']] + alt_osm_names + alt_punc_name
            )
            for name in all_names:
                locations_by_name[name].append(data)

            if resolution == ResolutionTypes.COUNTRY:
                found_countries[country_code] = data
            else:
                prev_country_importance = countries.get(country_code, ('', 0.))[1]
                if importance > prev_country_importance:
                    countries[country_code] = (data['country'], importance)

    print 'OSM resolution counts:', resolution_counts

    # Add back these missing countries to the data set.
    n_filled_in_countries = 0
    for country_code, (name, city_importance) in countries.iteritems():
        if country_code not in found_countries:
            n_filled_in_countries += 1
            data = dict(
                resolution=ResolutionTypes.COUNTRY,
                name=name,
                importance=city_importance + .05,
                country=name,
                country_code=country_code,
                population=10 ** 6,
                is_filled_in=True,
            )
            locations_by_name[name].append(data)
            found_countries[country_code] = data

    print 'Filled in %d missing countries from OSM' % n_filled_in_countries

    return locations_by_name, found_countries

def _is_ascii(string):
    return all(ord(c) < 128 for c in string)

def _get_resolution(data):
    for res_name, resolution in (
        (data['city'], ResolutionTypes.CITY),
        (data['county'], ResolutionTypes.ADMIN_2),
        (data['state'], ResolutionTypes.ADMIN_1),
        (data['country'], ResolutionTypes.COUNTRY),
    ):
        if res_name:
            if data['name'] == res_name:
                return resolution

            # Location name does not match the highest resolution field.
            if resolution == ResolutionTypes.COUNTRY:
                # There are some unusual results here; ignore them.
                return None
            if resolution == ResolutionTypes.CITY and _is_ascii(data['city']):
                # The city name seems generally more accurate, make the location name the
                # city name.
                data['name'] = data['city']
            else:
                # Otherwise, assume this location is a city.
                data['city'] = data['name']
            return ResolutionTypes.CITY

    raise ValueError("Location is missing names for all location levels")

def _should_skip_location(loc_data, locations_by_name):
    for other_location in locations_by_name[loc_data['name']]:
        if all(
            other_location[field] == loc_data[field]
            for field in ('name', 'city', 'admin_level_1', 'admin_level_2', 'country')
        ):
            # Some locations appear as twice in the data set. If we already saw a location with
            # the same location identifiers, just the keep the first (most important) entry.
            return True

        if (
            loc_data['resolution'] == ResolutionTypes.CITY and
            other_location['resolution'] == ResolutionTypes.CITY and
            all(
                loc_data[field] == other_location[field] or not loc_data[field]
                for field in ('name', 'city', 'admin_level_1', 'admin_level_2', 'country')
            )
        ):
            # Some cities appear as less specific versions of previous cities. Again just keep
            # the first entry.
            return True

    return False

def resolve_best_location(locations, is_osm):
    """
    Return the most important location from the options, if it is "sufficiently clear" which is
    most important. This is used to match the most important location for each name from the
    Geonames data to the OSM data.
    """
    if not locations:
        return None

    if len(locations) == 1:
        return locations[0]

    key = 'importance' if is_osm else 'population'
    locations.sort(key=lambda loc: loc[key], reverse=True)
    top_location = locations[0]
    next_location = locations[1]

    if is_osm:
        if top_location['importance'] > next_location['importance'] + .1:
            return top_location
    else:
        if (
            top_location['population'] > 3 * next_location['population'] or
            (
                top_location['population'] > 10 ** 6 and
                top_location['population'] > 2 * next_location['population']
            )
        ):
            return top_location

def find_osm_importances(osm_data_filepath, geo_locations_by_name, geo_locations_by_id):
    """
    For each Geonames location of non-trivial population, try to identify the corresponding
    location in the OSM dataset and record its importance score.
    """
    osm_locations_by_name, osm_countries = read_osm_locations(osm_data_filepath)

    location_importances = {}
    counts = dict((kind, set()) for kind in (
        'Unresolved geoname locations', 'Small location', 'Unresolved osm locations',
        'Dummy osm importance', 'Found match'
    ))

    for name, geo_locations in geo_locations_by_name.iteritems():
        for resolution in (
            ResolutionTypes.CITY, ResolutionTypes.ADMIN_1, ResolutionTypes.ADMIN_2,
            ResolutionTypes.COUNTRY
        ):
            candidate_locations = [
                loc for loc in geo_locations.itervalues() if loc['resolution'] == resolution
            ]
            if not candidate_locations:
                continue

            geo_location = resolve_best_location(candidate_locations, is_osm=False)
            if not geo_location:
                counts['Unresolved geoname locations'].update([
                    loc['id'] for loc in candidate_locations
                ])
                continue

            counts['Unresolved geoname locations'].update([
                loc['id'] for loc in candidate_locations if loc['id'] != geo_location['id']
            ])

            if geo_location['name'] != name:
                continue
            if (
                resolution != ResolutionTypes.COUNTRY and
                geo_location['population'] < MIN_POPULATION_THRESHOLD
            ):
                counts['Small location'].add(geo_location['id'])
                continue

            if resolution == ResolutionTypes.COUNTRY:
                best_match = osm_countries.get(geo_location['country_code'])
            else:
                matches = [
                    osm_location
                    for osm_location in osm_locations_by_name[name]
                    if (
                        osm_location['resolution'] == resolution and
                        osm_location['country_code'] == geo_location['country_code']
                    )
                ]
                best_match = resolve_best_location(matches, is_osm=True)

            if not best_match:
                counts['Unresolved osm locations'].add(geo_location['id'])
                continue

            if (best_match['importance'] < .41 or best_match['importance'] in (.5, .45)):
                counts['Dummy osm importance'].add(geo_location['id'])
                continue

            counts['Found match'].add(geo_location['id'])
            location_importances[geo_location['id']] = best_match['importance']

    print '##########################'
    print 'All locations matches'
    for kind, ids in counts.iteritems():
        print '%s: %d' % (kind, len(ids))

    print '##########################'
    print 'Country matches'
    print 'Matches: ', len([
        id_ for id_ in counts['Found match']
        if geo_locations_by_id[id_]['resolution'] == ResolutionTypes.COUNTRY
    ])
    for kind, ids in counts.iteritems():
        if kind != 'Found match':
            locs = []
            for id_ in ids:
                geo_location = geo_locations_by_id[id_]
                if (
                    id_ not in location_importances and
                    geo_location['resolution'] == ResolutionTypes.COUNTRY
                ):
                    locs.append((geo_location['name'], geo_location['population']))
            print '## %s: %d' % (kind, len(locs))
            for loc in locs:
                print loc

    return location_importances

def get_data_sets(geo_locations_by_id, location_importances):
    """
    Make data sets using Geonames locations (this includes the input features for each location
    and the importance labels for those of which we were able to find the match in OSM data)
    """
    training_sets = {
        # values are lists of ids, features, and labels
        resolution: ([], [], [])
        for resolution in (ResolutionTypes.CITY, ResolutionTypes.ADMIN_1, ResolutionTypes.ADMIN_2)
    }
    predict_sets = {
        resolution: ([], [])
        for resolution in (ResolutionTypes.CITY, ResolutionTypes.ADMIN_1, ResolutionTypes.ADMIN_2)
    }
    n_locs_missing_country_importance = dict((res, 0) for res in training_sets)

    for id_, location in geo_locations_by_id.iteritems():
        if location['resolution'] == ResolutionTypes.COUNTRY:
            continue
        if location['country_id'] not in location_importances:
            n_locs_missing_country_importance[location['resolution']] += 1
            continue
        if location['population'] < MIN_POPULATION_THRESHOLD:
            continue

        country = geo_locations_by_id[location['country_id']]
        country_importance = location_importances[country['id']]
        population_fraction = float(location['population']) / country['population']

        if id_ in location_importances:
            ids, features, labels = training_sets[location['resolution']]
            ids.append(id_)
            features.append([country_importance, population_fraction])
            labels.append(location_importances[id_])
        else:
            ids, features = predict_sets[location['resolution']]
            ids.append(id_)
            features.append([country_importance, population_fraction])

    print 'Locations missing country importance: ', n_locs_missing_country_importance

    return training_sets, predict_sets

def train_models(training_sets, geo_locations_by_id, location_importances, show_plot):
    """
    Train a model for each resolution type. Print the training / test loss for some training / test
    splits to get an idea of how well the models perform, and then return the final models trained
    on all of the data.
    """
    models = {}

    for i, resolution in enumerate(
        (ResolutionTypes.CITY, ResolutionTypes.ADMIN_1, ResolutionTypes.ADMIN_2)
    ):
        training_ids, training_features, training_labels = training_sets[resolution]
        print '##########################'
        print 'Training model for', resolution
        print 'Num training samples:', len(training_ids)

        X = np.log(training_features)
        Y = np.array(training_labels)
        weights = np.maximum(Y - .4, 0)

        print 'Range of importances: %f - %f' % (Y.min(), Y.max())

        train_scores = []
        test_scores = []
        n_trials = 300 if resolution == ResolutionTypes.CITY else 1000
        for t in range(n_trials):
            X_train, X_test, Y_train, Y_test, weights_train, weights_test = train_test_split(
                X, Y, weights, train_size=.9
            )
            model = clone(MODELS_TYPES[resolution])
            model.fit(X_train, Y_train, sample_weight=weights_train)

            train_scores.append(model.score(X_train, Y_train, sample_weight=weights_train))
            test_scores.append(model.score(X_test, Y_test, sample_weight=weights_test))

        print 'Average R2 on training set: ', sum(train_scores) / n_trials
        print 'Average R2 on test set: ', sum(test_scores) / n_trials

        model = clone(MODELS_TYPES[resolution])
        model.fit(X, Y, sample_weight=weights)
        models[resolution] = model

        predicts = model.predict(X)
        weighted_errors = weights * (predicts - Y) ** 2
        loc_errors = zip(training_ids, predicts, weighted_errors)
        loc_errors.sort(key=lambda error: error[2], reverse=True)
        print 'Biggest errors:'
        for id_, prediction, weighted_error in loc_errors[:10]:
            location = geo_locations_by_id[id_]
            print (
                location['resolution'], location['name'], location['country'],
                location_importances[id_], prediction
            )

        if show_plot:
            plt.figure(i + 1)
            plt.title(resolution)
            plt.plot(predicts, Y, '.')
            plt.axis([.4, .8, .4, .8])

    return models

def make_predictions(
    models, training_sets, predict_sets, geo_locations_by_id, location_importances
):
    """
    Make importance predictions for all Geonames locations (including those in the training set).
    For locations whose country does not have an importance score, we assign it a default
    importance.
    """
    ids_with_features = set()
    for data_sets in (training_sets, predict_sets):
        for data_set in data_sets.itervalues():
            ids_with_features.update(data_set[0])

    predictions = {}
    default_country_predictions = []
    default_predictions = []

    for id_, location in geo_locations_by_id.iteritems():
        if location['resolution'] == ResolutionTypes.COUNTRY:
            if id_ in location_importances:
                predictions[id_] = location_importances[id_]
            else:
                predictions[id_] = DEFAULT_IMPORTANCE[ResolutionTypes.COUNTRY]
                default_country_predictions.append(location)
        else:
            if id_ not in ids_with_features:
                predictions[id_] = DEFAULT_IMPORTANCE[location['resolution']]
                if location['population'] > MIN_POPULATION_THRESHOLD:
                    default_predictions.append(location)

    print '##########################'
    print 'Default country predictions:', len(default_country_predictions)
    print 'Default other predictions:', len(default_predictions)

    for resolution, model in models.iteritems():
        training_ids, training_features, training_labels = training_sets[resolution]
        X = np.log(training_features)
        training_predictions = model.predict(X)
        predictions.update(dict(zip(training_ids, training_predictions)))

        predict_ids, predict_features = predict_sets[resolution]
        X = np.log(predict_features)
        predict_predictions = model.predict(X)
        predictions.update(zip(predict_ids, predict_predictions))

        print 'Num %s locations trained, only predicted: %d, %d' % (
            resolution, len(training_ids), len(predict_ids)
        )

    return predictions

def print_diffs(importance_filepath_1, importance_filepath_2):
    """
    Use this method to print the top differences between two different files for estimated
    importances.
    """
    with open(importance_filepath_1) as f:
        importance_1 = json.load(f)
    with open(importance_filepath_2) as f:
        importance_2 = json.load(f)
    assert set(importance_1.keys()) == set(importance_2.keys())
    _, locations_by_id = geonames.load_data()

    diffs = [(id_, importance_1[id_], importance_2[id_]) for id_ in importance_1]
    diffs.sort(key=lambda info: abs(info[1] - info[2]), reverse=True)
    for id_, i1, i2 in diffs:
        if abs(i1 - i2) < .1:
            break

        location = locations_by_id[int(id_)]
        print location['resolution'], location['name'], location['country'], i1, i2

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('osm_filepath')
    parser.add_argument('output_filepath')
    parser.add_argument('--plot', action='store_true')
    args = parser.parse_args()

    try:
        run(args.osm_filepath, args.output_filepath, args.plot)
    except:
        type, value, tb = sys.exc_info()
        traceback.print_exc()
        pdb.post_mortem(tb)

