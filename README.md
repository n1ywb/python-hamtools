# N1YWB Python Ham Radio Tools #

This package includes several Python modules and scripts of interest to the
radio amateur.

This stuff is very alpha. Really just a bunch of quick hacks I slapped
together. But I will take bug reports and try to improve things over time.

Includes:

* QRZ.com lookup
* ADIF file parsing
* Cabrillo file parsing
* cty.dat parsing and querying
* Logged callsign georeferencing
* Geojson output
* KML output

## geolog ##

The geolog script reads a log file in ADIF or Cabrillo format, georeferences
the callsigns therein, and outputs a set of GeoJSON and KML files suitable for
importing in Google Earth, Quantum GIS (QGIS), ArcGIS, etc.

I've only tested it with ARRL 10m contest logs. It will probably barf on other
cabrillo files with different formats. If so, please file a bug report.

To georeference calls the program first looks it up on QRZ. If QRZ has no
lat/lon information for the call, the program uses cty.dat. This will place the
point in the center of the call area based on the prefix, so it's not very
accurate, but better than nothing.

Should probably factor out the cabrillo parser into a separate module.

To avoid typing your QRZ username and password each time, you may save these to
a config file at `$HOME/.geologrc`. You may also specify the config file
location explicity with the `-c` command line option. See the included
`geologrc_example` file. You may also use the config file to override the
default QRZ cache file location.

## hamtools.adif ##

The adif module implements a subset of the ADIF standard for reading and
writing.

## hamtools.qrz ##

Simple interface to the QRZ.com XML data service.

To improve speed, this module caches QRZ.com XML responses in
`$HOME/.qrz_cache`. You may wish to periodically delete this file to avoid
stale data.

## hamtools.ctydat ##

Straight port of the YFKLog cty.dat parsing/lookup code. I haven't tested this
extensively, it's probably buggy.

## hamtools.kml ##

Simple KML generation based on minidom.

## vk ##

A very trivial voice keyer script which plays an audio file while
simultaniously keying a radio via the serial port. Requires pyserial.

