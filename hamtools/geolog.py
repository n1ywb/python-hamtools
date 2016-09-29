#!/usr/bin/env python
#
# Copyright 2009, 2012, 2014 by Jeffrey M. Laughlin
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import argparse
import ConfigParser
import logging
import os
import sys
import traceback
from pkg_resources import resource_stream
import geojson as gj
from hamtools import adif
from hamtools.ctydat import CtyDat, InvalidDxcc, InvalidCallsign
from hamtools import kml
from hamtools import qrz
import requests
import requests_cache


log = logging.getLogger(__name__)

# log.setLevel(logging.INFO)

# 1. Load log
# 2. Georeference log
# 3. Cache georeferenced calls
# 4. Output GeoJSON

CABRILLO_FIELDS = ['header', 'freq', 'mode', 'date', 'time',
                   'from_call', 'sent_rst', 'sent_ex', 'call', 'receved_rst',
                   'received_ex']

CACHEPATH = os.path.join(os.environ['HOME'], '.qrz_cache')


class OperatorGeoRefFail(Exception): pass


class GeoRefFail(Exception): pass


class GeoRefError(Exception): pass


class NullLoc(GeoRefError): pass


class NotFound(GeoRefError): pass


class QrzReferencer(object):
    def __init__(self, session):
        self.session = session

    ## TODO memoize and cache
    def reference(self, callsign):
        """Returns lon, lat from QRZ"""
        try:
            rec = self.session.qrz(callsign)
            if None in (rec['lat'], rec['lon']):
                raise NullLoc(callsign)
            lat, lon = rec['lat'], rec['lon']
            log.debug("qrz rec %s" % rec)
        except qrz.NotFound, e:
            raise NotFound(callsign)
        except qrz.QrzError, e:
            raise GeoRefError(*e.args)
        return lon, lat


class CtyDatReferencer(object):
    def __init__(self, ctydat):
        self.ctydat = ctydat

    def reference(self, callsign):
        """Returns lon, lat from ctydat"""
        try:
            dxcc = self.ctydat.getdxcc(callsign)
        except (InvalidDxcc, InvalidCallsign):
            raise GeoRefError(callsign)
        lat = float(dxcc['lat'])
        lon = float(dxcc['lon']) * -1
        return lon, lat


class FCCReferencer(object):
    PREFIXES = list('aknw')
    CACHEPATH = os.path.join(os.environ.get('XDG_CACHE_HOME', os.environ['HOME']), '.callook_cache')
    requests_cache.install_cache(CACHEPATH)
    def reference(self, callsign):
        if callsign[0].lower() not in self.PREFIXES:
            raise NotFound(callsign)
        r = requests.get("https://callook.info/%s/json" % callsign)
        if r.status_code == 404:
            raise NotFound(callsign)
        if r.status_code != 200:
            raise GeoRefError(r.status_code)
        try:
            data = r.json()
        except ValueError:
            raise GeoRefError('bad json')
        if data['status'] != 'VALID':
            raise GeoRefError('invalid')
        raw_lon = data['location']['longitude']
        raw_lat = data['location']['latitude']
        if not raw_lon or not raw_lat:
            raise GeoRefError("No location data")
        try:
            lon = float(data['location']['longitude'])
            lat = float(data['location']['latitude'])
            return lon, lat
        except Exception, e:
            log.debug(data)
            raise


class Log(object):
    def __init__(self):
        self.qsos = []
        self.callsign = None

    @staticmethod
    def from_cabrillo(logfile):
        self = Log()
        for line in logfile:
            if line.startswith("QSO"):
                qso = dict(zip(CABRILLO_FIELDS, line.split()))
                # Pygeojson just repr's numbers, which doesn't add .0 to
                # floats, which makes them JSON ints, which QGIS won't allow to
                # use for a graduated scale.
                qso['time'] = float(qso['time'] + '.000000001')
                try:
                    freq = float(qso['freq']) + 0.00000001
                except ValueError:
                    pass
                else:
                    qso['freq'] = freq
                self.qsos.append(qso)
                log.debug(qso)
            elif line.startswith("CALLSIGN:"):
                self.callsign = line.split()[1]
                log.info("Callsign: %s" % self.callsign)
        log.info("Read %d records" % len(self.qsos))
        return self

    @staticmethod
    def from_adif(logfile):
        # TODO check for invalid ADIF file
        self = Log()
        log = adif.Reader(logfile)
        for qso in log:
            try:
                del qso['app_datetime_on']
            except KeyError:
                pass
            try:
                del qso['app_datetime_off']
            except KeyError:
                pass
            self.qsos.append(qso)
        if self.qsos:
            qso = self.qsos[0]
            self.callsign = qso.get('station_callsign', None)
            if not self.callsign:
                self.callsign = qso.get('operator', None)
        return self

    def _georef(self, callsign):
        for d in self.drivers:
            try:
                return d.reference(callsign)
            except GeoRefError, e:
                log.warning("%r failed on call %s: %s", d, callsign, e)
        else:
            raise GeoRefFail(callsign)

    def georeference(self, sess, ctydat):
        drivers = self.drivers = []
        sess and drivers.append(QrzReferencer(sess))
        drivers.append(FCCReferencer())
        ctydat and drivers.append(CtyDatReferencer(ctydat))

        if not drivers:
            raise Exception("No georef drivers")

        if not self.callsign:
            raise OperatorGeoRefFail("Unable to determine op callsign from log")

        try:
            self.lon, self.lat = self._georef(self.callsign)
        except GeoRefFail:
            raise OperatorGeoRefFail("Failed to georeference operator callsign", self.callsign)

        for qso in self.qsos:
            try:
                qso['lon'], qso['lat'] = self._georef(qso['call'])
            except GeoRefFail:
                log.warning("Failed to georef call %s", qso['call'])

    def geojson_dumps(self, *args, **kwargs):
        qth, pointsFC, linesFC = self.geojson()
        r = dict(qth=qth, pointsFC=pointsFC, linesFC=linesFC)
        return gj.dumps(r)

    def geojson(self):
        qth = gj.Feature(geometry=gj.Point((self.lon, self.lat)))
        points = []
        lines = []
        for qso in self.qsos:
            point, line = None, None
            coords = qso.get('lon', None), qso.get('lat', None)
            if None not in coords:
                point = gj.Point(coords)
                line = gj.LineString([
                    (self.lon, self.lat),
                    coords
                ])
            points.append(gj.Feature(geometry=point,
                                     properties=qso))
            lines.append(gj.Feature(geometry=line,
                                    properties=qso))
        pointsFC = gj.FeatureCollection(points)
        linesFC = gj.FeatureCollection(lines)
        return qth, pointsFC, linesFC

    def write_kml(self, file):
        dom = kml.KML()
        doc = dom.createDocument(self.callsign + " log")
        folder = dom.createFolder(self.callsign + " log")
        doc.appendChild(folder)
        dom.root.appendChild(doc)
        callnode = dom.createPlacemark(self.callsign, self.lat, self.lon)
        folder.appendChild(callnode)
        for qso in self.qsos:
            call, lat, lon = qso['call'], qso["lat"], qso["lon"]
            callnode = dom.createPlacemark(call, lat, lon)
            callnode2 = dom.createPlacemark(call, lat, lon)
            theline = dom.createLineString(
                ((lat, lon, 0), (self.lat, self.lon, 0)),
                tessel=True)
            folder.appendChild(callnode2)
            callnode.appendChild(theline)
            callnode.removeChild(callnode.childNodes[1])
            folder.appendChild(callnode)
        dom.writepretty(file)


def geolog(logfilepath, outfile, username, password, cachepath, ctydatflo):
    with open(logfilepath) as logfile:
        line = logfile.next()

    with open(logfilepath) as logfile:
        if line.startswith('START-OF-LOG'):
            log.info("Opened Cabrillo format log %r" % logfile)
            qsolog = Log.from_cabrillo(logfile)
        else:
            log.info("Opened ADIF format log %r" % logfile)
            qsolog = Log.from_adif(logfile)

    ctydat = CtyDat(ctydatflo)
    with qrz.Session(username, password, cachepath) as sess:
        qsolog.georeference(sess, ctydat)

    points, lines = qsolog.geojson_dumps(sort_keys=True)

    pointfile = '_'.join((outfile, 'points.geojson'))
    with open(pointfile, "w") as pointfile:
        pointfile.write(points)

    linefile = '_'.join((outfile, 'lines.geojson'))
    with open(linefile, "w") as linefile:
        linefile.write(lines)

    kmlfile = ''.join((outfile, '.kml'))
    with open(kmlfile, "w") as kmlfile:
        qsolog.write_kml(kmlfile)


def main(argv=None):
    if argv is None:
        argv = sys.argv

    parser = argparse.ArgumentParser(
        description=
        """Read ham log and output GIS data for callsigns worked. Output files will be
prefixed with output path. E.g. given "foo/bar", the following files will be
created: "foo/bar_points.geojson", "foo/bar_lines.geojson", and "foo/bar.kml"
""")
    parser.add_argument('infile', type=str,
                        help='Input log file (ADIF or Cabrillo)')
    parser.add_argument('outpath', type=str,
                        help='Output path prefix')
    parser.add_argument('-c', '--cfg', type=str,
                        help='Config file path', default=os.path.join(os.environ['HOME'], '.geologrc'))
    parser.add_argument('-v', '--verbose', type=bool,
                        help='Turn on additional output', default=False)
    args = parser.parse_args(argv[1:])

    cfg = ConfigParser.SafeConfigParser()

    cfg.read(args.cfg)

    try:
        un = cfg.get('qrz', 'username')
    except ConfigParser.Error:
        un = raw_input("QRZ.com user name:")

    try:
        pw = cfg.get('qrz', 'password')
    except ConfigParser.Error:
        pw = raw_input("QRZ.com password (not stored):")

    try:
        cachepath = cfg.get('qrz', 'cachepath')
    except ConfigParser.Error:
        cachepath = CACHEPATH

    try:
        cachepath = cfg.get('qrz', 'cachepath')
    except ConfigParser.Error:
        cachepath = CACHEPATH

    try:
        ctydatpath = cfg.get('geolog', 'cachepath')
        ctydatflo = open(ctydatpath)
    except ConfigParser.Error:
        ctydatflo = resource_stream(__name__, "ctydat/cty.dat")

    log.info("QRZ cache: %s" % cachepath)

    geolog(args.infile, args.outpath, un, pw, cachepath, ctydatflo)

    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
