# -*- coding: utf-8 -*-
import re
import json
import pdb
import requests
import sys
import traceback
from collections import defaultdict

from bs4 import BeautifulSoup
from bs4.element import NavigableString, CData, Comment

from geonamescache.geonames.utils import ResolutionTypes, standardize_loc_name
from geonamescache.geonames.geonames import load_data


"""
Fetches alternate names from wikipedia for locations in the geonames data set.
"""

MIN_POPULATION_THRESHOLD = 10 ** 4
MIN_AMBIG_IMPORTANCE_THRESHOLD = .5

def text_attrs(base):
    """
    Yield `(text, attr)` pairs for all descendants of `base`.
    """
    def _text_attrs(obj, attrs):
        if isinstance(obj, (NavigableString, CData, Comment)):
            yield (obj, dict(attrs))
        else:
            attrs = attrs.copy()
            for k, attr in obj.attrs.iteritems():
                attrs[k].append(attr)

            for child in obj.children:
                for child_obj in _text_attrs(child, attrs):
                    yield child_obj

    return _text_attrs(base, defaultdict(list))


def css_style(raw_style):
    """
    Return a dictionary of CSS `(property, value)` pairs from (potentially multiple)
    "property:value; property:value" CSS styling strings.
    """
    if isinstance(raw_style, basestring):
        raw_style = [raw_style]

    concatenated_style = u';'.join(raw_style)
    property_values = filter(bool, map(unicode.strip, concatenated_style.split(';')))

    return dict(pv.split(':') for pv in property_values)

def is_valid_wiki_page(soup):
    """
    Returns whether the given web page is a valid wikipedia content page.
    """
    first_heading = soup('h1', {'id' : 'firstHeading'})
    if not first_heading:
        return False

    page_name = first_heading[0].get_text()
    if page_name == 'Search results':
        return False

    mw_content_text = soup('div', {'id' : 'mw-content-text'})
    if not mw_content_text:
        return False

    paragraphs_text = []
    for paragraph in mw_content_text[0]('p', recursive=False):
        # Don't include any `text` in `paragraph` which has 'font-size' in the CSS styling or is set
        # to 'display: none'.
        paragraph_text = []
        for text, attrs in text_attrs(paragraph):
            style = css_style(attrs.get('style', []))
            if 'font-size' in style or style.get('display', '') == 'none':
                continue

            paragraph_text.append(text)

        # Don't include empty paragraphs.
        paragraph_text = ''.join(paragraph_text)
        if not paragraph_text:
            continue

        paragraphs_text.append(paragraph_text)

    if not paragraphs_text:
        return False

    first_paragraph = paragraphs_text[0]
    if not first_paragraph or re.findall(r'refer[s]? to:', first_paragraph):
        return False

    return True

def get_wikipedia(search_term):
    """
    Get the alternate names from the wikipedia search term. Returns None if the request failed
    or if there was no real page found.
    """

    url = 'https://en.wikipedia.org/wiki/%s' % search_term.replace(' ', '_')
    headers = {'User-agent': 'Mozilla/5.0'}

    try:
        req = requests.get(url, headers=headers, timeout=10)
    except requests.RequestException:
        print 'Warning: could not fetch results for ', search_term
        return None

    soup = BeautifulSoup(req.text, 'lxml')
    if not is_valid_wiki_page(soup):
        return None

    alt_names = []

    first_heading = soup('h1', {'id' : 'firstHeading'})
    page_name = first_heading[0].get_text()
    alt_names.append(page_name)

    disambig_links = [a for a in soup.select('.hatnote .mw-disambig') if a.name == 'a']
    alt_names.extend([link.text for link in disambig_links])

    for element in soup.select('.hatnote'):
        redirects_here_match = re.match(r'"(.*)" redirects here', element.text)
        if redirects_here_match:
            alt_names.append(redirects_here_match.groups()[0])

    alt_names = set(fix_name(name) for name in alt_names)
    alt_names.discard(fix_name(search_term))

    return list(alt_names)

def fix_name(name):
    name = name.split('(')[0].strip()
    name = name.split(',')[0].strip()
    return standardize_loc_name(name)

def search(query):
    result = get_wikipedia(query)

    if result is None:
        if ' ' in query:
            result = get_wikipedia(query.replace(' ', '-'))

    if result is None:
        if '(' in query:
            result = get_wikipedia(query.split('(')[0].strip())

    if result is None:
        if ',' in query:
            result = get_wikipedia(query.split(',')[0].strip())

    return result

def get_adjusted_importance(location):
    modifier = 0.
    if location['resolution'] == ResolutionTypes.COUNTRY:
        modifier = .2
    elif location['resolution'] == ResolutionTypes.ADMIN_1:
        modifier = -.15
    elif location['resolution'] == ResolutionTypes.ADMIN_2:
        modifier = -.2

    return location['estimated_importance'] + modifier

def run(out_filename):
    """
    Find the alternate names of locations in the geonames data set and write them to an output file.
    """
    locations_by_name, locations_by_id = load_data()

    # ID to list of alternative names
    alt_names_found = {}
    # Name to biggest population of location with this name
    ambig_locs = {}
    # Alternate name to location's name and population (if the alternate name collides with
    # another location name)
    ambig_alts = {}
    # Name to the top location's importance ond country
    resolved_locs = {}

    counts = dict((kind, 0) for kind in (
        'ambiguous name', 'no wiki page found', 'no alt names found', 'ambiguous alt name'
    ))
    hits = 0

    for i, (name, locations_with_name) in enumerate(locations_by_name.iteritems()):
        if i % 300 == 299:
            print 'Search number', i
            print counts, hits
            break

        if not locations_with_name:
            continue

        location = None
        if len(locations_with_name) == 1:
            candidate = locations_with_name.values()[0]
            if candidate['population'] > MIN_POPULATION_THRESHOLD:
                location = candidate
        else:
            locations_by_importance = sorted(
                locations_with_name.values(), key=lambda loc: get_adjusted_importance(loc),
                reverse=True
            )
            top_importance = get_adjusted_importance(locations_by_importance[0])
            next_importance = get_adjusted_importance(locations_by_importance[1])
            if (
                top_importance > MIN_AMBIG_IMPORTANCE_THRESHOLD and
                top_importance - next_importance > .12
            ):
                candidate = locations_by_importance[0]
                if candidate['population'] > MIN_POPULATION_THRESHOLD:
                    location = candidate
                    resolved_locs[name] = (top_importance, location['country'])

        if not location:
            ambig_locs[name] = max(
                loc.get('population', 0) for loc in locations_with_name.values()
            )
            counts['ambiguous name'] += 1
            continue

        if location['name'] != name:
            # only search for location's real name
            continue

        result = search(name)
        if result is None:
            counts['no wiki page found'] += 1
            continue

        if not result:
            counts['no alt names found'] += 1
            continue

        importance = get_adjusted_importance(location)
        good_alt_names = []

        for alt_name in result:
            skip_name = False
            locations_with_alt_name = locations_by_name.get(alt_name, {})
            for alt_location in locations_with_alt_name.itervalues():
                if alt_location['id'] == location['id']:
                    continue
                alt_importance = get_adjusted_importance(alt_location)
                if alt_location['name'] == alt_name and alt_importance + .1 > importance:
                    skip_name = True
                    break
                if alt_location['name'] != alt_name and alt_importance > importance + .1:
                    skip_name = True
                    break

            if skip_name:
                ambig_alts[alt_name] = (location['name'], location['population'])
            else:
                good_alt_names.append(alt_name)

        if not good_alt_names:
            counts['ambiguous alt name'] += 1
            continue

        hits += 1
        alt_names_found[location['id']] = good_alt_names

    # main alternate names file
    with open(out_filename, 'w') as out:
        json.dump(alt_names_found, out)

    # log cases we skipped
    with open('ambig_names.txt', 'w') as out:
        for loc in sorted(ambig_locs.iteritems(), key=lambda pair: pair[1], reverse=True):
            out.write(str(loc) + '\n')
    with open('ambig_alt_names.txt', 'w') as out:
        for loc in sorted(ambig_alts.iteritems(), key=lambda info: info[-1], reverse=True):
            out.write(str(loc) + '\n')
    with open('resolved.txt', 'w') as out:
        for loc in sorted(
            resolved_locs.iteritems(), key=lambda pair: pair[1][0], reverse=True
        ):
            out.write(str(loc) + '\n')

if __name__ == '__main__':
    try:
        run(sys.argv[1])
    except:
        type, value, tb = sys.exc_info()
        traceback.print_exc()
        pdb.post_mortem(tb)
