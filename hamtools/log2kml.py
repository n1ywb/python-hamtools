#!/usr/bin/env python
#
# Copyright 2009, 2012 by Jeffrey M. Laughlin
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

import sys
import qrz
import kml
import traceback

class Log(object):
    def __init__(self, call, lat, lon):
        dom = self.dom = kml.KML()
        doc = dom.createDocument(call + " log")
        folder = self.folder = dom.createFolder(call + " log")
        doc.appendChild(folder)
        dom.root.appendChild(doc)
        callnode = self.dom.createPlacemark(call, lat, lon)
        self.folder.appendChild(callnode)
        self.lat = lat
        self.lon = lon

    def add_qso(self, qrzsession, call):
        callrec = qrzsession.qrz(call)
        lat, lon = callrec['lat'], callrec['lon']
        assert lat is not None
        assert lon is not None
        callnode = self.dom.createPlacemark(call, callrec["lat"], callrec["lon"])
        callnode2 = self.dom.createPlacemark(call, callrec["lat"], callrec["lon"])
        theline = self.dom.createLineString(((callrec["lat"], callrec["lon"],0),(self.lat,self.lon,0)), tessel=True)
        self.folder.appendChild(callnode2)
        callnode.appendChild(theline)
        callnode.removeChild(callnode.childNodes[1])
        self.folder.appendChild(callnode)

    def save(self, file):
        self.dom.writepretty(file)

def log2kml(logfile, outfile, qrzsess, call, lat, lon):
    mylog = Log(call, lat, lon)
    for line in logfile:
        if line.startswith("QSO"):
            callsign = line[55:67].strip()
            print '"' + callsign + '"'
            try:
                mylog.add_qso(qrzsess, callsign)
            except Exception:
                traceback.print_exc()
    mylog.save(outfile)


if __name__ == "__main__":
    logfile = open(sys.argv[1])
    outfile = open(sys.argv[2], "w")

    qrzs = qrz.Session("n1ywb", raw_input("password:"))

    log2kml(logfile, outfile, qrzs, "n1ywb", 44.197227, -72.486237)

