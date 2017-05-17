Geonames Cache
==============

Our library to maintain our locations data files, data format, and search interface. We currently have data from Geonames and from OpenStreetMaps.

Installation
------------

Run: ::

    $ python setup.py install

Usage
-----

A simple usage example:

::

    from geonamescache.geonames.data_source import DataSource

    data_source = DataSource()
    print data_source.all_locations_search('Lebanon')
    print data_source.get_location_by_id(6252001) # USA


Geonames data
-------


Data from http://download.geonames.org/export/dump/. Using the cities5000 data set, this contains ~50000 cities, ~40000 admin level 2 districts, ~4000 admin level 1 districts, and ~250 countries. The above link also documents the fields provided for each type of location.

We currently use Geonames as the data source in primer-core.

**See the README in geonamescache/geonames for how to manage the data.**

OpenStreetMaps data
-------

Data from https://github.com/OSMNames/OSMNames/releases/tag/v1.1. This contains the 100K most important locations according to counts of wikipedia links, including ~75000 cities, ~15000 admin level 2 districts, ~2000 admin level 1 districts, and ~250 countries. http://osmnames.org/download/ documents the fields provided for each location.

Note: this data source appears to be missing some key locations such as Vienna, Bangkok, Seoul, Cairo, etc. as well as some fields such as the admin level 1 of Chicago. (We think the missing locations is from having an incorrect importance score derived from wikipedia data, and that nominatim has more accurate data).

Getting other data fields
-------

We also have scripts to 

1. fetch alternate names for locations from wikipedia
2. compute estimated importance scores for locations for the Geonames data set
