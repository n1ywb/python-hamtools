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

import geojson as gj

from ctydat import CtyDat, InvalidDxcc
import kml
import qrz

log = logging.getLogger('geolog')
#log.setLevel(logging.INFO)

# 1. Load log
# 2. Georeference log
# 3. Cache georeferenced calls
# 4. Output GeoJSON

CABRILLO_FIELDS = ['header', 'freq', 'mode', 'date', 'time',
    'from_call', 'sent_qst', 'sent_ex', 'to_call', 'receved_qst',
    'received_ex']

CACHEPATH = os.path.join(os.environ['HOME'], '.qrz_cache')

class NullLoc(Exception): pass

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
                qso['time'] = float(qso['time'] + '.000000001')
                qso['freq'] = float(qso['freq'] + '.000000001')
                self.qsos.append(qso)
                log.debug(qso)
            elif line.startswith("CALLSIGN:"):
                self.callsign = line.split()[1]
                log.info("Callsign: %s" % self.callsign)
        log.info("Read %d records" % len(self.qsos))
        return self

    def georeference(self, sess, ctydat):
        try:
            rec = sess.qrz(self.callsign)
            if None in (rec['lat'], rec['lon']):
                raise NullLoc()
            self.lat, self.lon = rec['lat'], rec['lon']
            log.debug("qrz rec %s" % rec)
        except NullLoc:
            log.warning("QRZ lookup failed for %s, no location data" % self.callsign)
            raise
        except qrz.NotFound, e:
            log.warning("QRZ lookup failed for %s, not found" % self.callsign)
            raise
        except Exception, e:
            log.warning("QRZ lookup failed for %s" % self.callsign, exc_info=True)
            raise

        for qso in self.qsos:
            qso['lat'], qso['lon'] = None, None
            try:
                rec = sess.qrz(qso['to_call'])
                log.debug("qrz rec %s" % rec)
                if rec['call'] != qso['to_call']:
                    log.warning("qrz %s != %s" % (rec['call'],
                                    qso['to_call']))
                if None in (rec['lat'], rec['lon']):
                    raise NullLoc()
                qso['lat'], qso['lon'] = rec['lat'], rec['lon']
            except Exception, e:
                if isinstance(e, qrz.NotFound):
                    log.warning("QRZ lookup failed for %s, not found" % qso['to_call'])
                elif isinstance(e, NullLoc):
                    log.warning("QRZ lookup failed for %s, no location data" % qso['to_call'])
                else:
                    log.warning("QRZ lookup failed for %s" % qso['to_call'], exc_info=True)
                try:
                    dxcc = ctydat.getdxcc(qso['to_call'])
                    qso['lat'] = float(dxcc['lat'])
                    qso['lon'] = float(dxcc['lon']) * -1
                except Exception:
                    log.warning("cty.dat lookup failed for %s" % qso['to_call'], exc_info=True)
                    raise

    def geojson_dumps(self, *args, **kwargs):
        points = []
        lines = []
        for qso in self.qsos:
            point = gj.Point((qso['lon'], qso['lat']))
            points.append(gj.Feature(geometry=point,
                                 properties=qso))
            line = gj.LineString([
                        (self.lon, self.lat),
                        (qso['lon'], qso['lat'])
            ])
            lines.append(gj.Feature(geometry=line,
                                 properties=qso))
        return (
            gj.dumps(gj.FeatureCollection(points), *args, **kwargs),
            gj.dumps(gj.FeatureCollection(lines), *args, **kwargs),
        )

    def write_kml(self, file):
        dom = kml.KML()
        doc = dom.createDocument(self.callsign + " log")
        folder = dom.createFolder(self.callsign + " log")
        doc.appendChild(folder)
        dom.root.appendChild(doc)
        callnode = dom.createPlacemark(self.callsign, self.lat, self.lon)
        folder.appendChild(callnode)
        for qso in self.qsos:
            to_call, lat, lon = qso['to_call'], qso["lat"], qso["lon"]
            callnode = dom.createPlacemark(to_call, lat, lon)
            callnode2 = dom.createPlacemark(to_call, lat, lon)
            theline = dom.createLineString(
                ((lat, lon, 0), (self.lat, self.lon, 0)),
                tessel=True)
            folder.appendChild(callnode2)
            callnode.appendChild(theline)
            callnode.removeChild(callnode.childNodes[1])
            folder.appendChild(callnode)
        dom.writepretty(file)

def geolog(logfile, outfile, username, password, cachepath):
    with open(logfile) as logfile:
        log.info("Opened %r" % logfile)
        qsolog = Log.from_cabrillo(logfile)

    with open('/home/jeff/Downloads/ctydat/cty.dat') as ctydat:
        ctydat = CtyDat(ctydat)
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

    logging.basicConfig(level=logging.INFO)

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

    log.info("QRZ cache: %s" % cachepath)

    geolog(args.infile, args.outpath, un, pw, cachepath)

    return 0

if __name__ == "__main__":
    sys.exit(main())

