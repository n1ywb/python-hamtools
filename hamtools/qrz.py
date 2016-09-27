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

import httplib, urllib
from xml.dom import minidom
import sys
import os
import sqlite3
import logging

log = logging.getLogger(__name__)

CACHEPATH = os.path.join(os.environ.get('XDG_CACHE_HOME', os.environ['HOME']), '.qrz_cache')

testSessionXML = """\
<?xml version="1.0" ?> 
<QRZDatabase xmlns="http://xml.qrz.com">
  <Session>
    <Key>2331uf894c4bd29f3923f3bacf02c532d7bd9</Key> 
    <GMTime>Sun Aug 16 03:51:47 2006</GMTime> 
  </Session>
</QRZDatabase>
"""

class QrzError(Exception):
    pass

class NotFound(QrzError):
    pass

class CallMismatch(QrzError):
    pass

class QrzRequestError(QrzError):
    pass

class Callsign(object):
    conversions = dict(
        lat=float,
        lon=float,
    )

    def __init__(self, node):
        self.node = node

    def __getitem__(self, key):
        try:
            value = self.node.getElementsByTagName(key)[0].firstChild.data
        except IndexError, e:
            return None
        if key in self.conversions.keys():
            value = self.conversions[key](value)
        return value

class Session(object):
    def __init__(self, user=None, passwd=None, cachepath=CACHEPATH, key=None):
        # post http://xml.qrz.com/xml?username=user;password=passwdo
        # self.key = minidom parse key
        # check for alert or error
        if not key:
            xml = self.request(dict(username=user, password=passwd))
            log.debug(xml)
            dom = minidom.parseString(xml)
            session = dom.getElementsByTagName("Session")[0]
            self.checkErr(session)
            key = session.getElementsByTagName("Key")[0].firstChild.data
        self.key = key
        self.db = sqlite3.connect(cachepath)
        self.db.text_factory = str
        try:
            self.db.execute("""
                create table dict (
                    key,
                    val
                )
            """)
            self.db.commit();
        except sqlite3.OperationalError:
            log.warning("maybe cache table exists?")

    def request(self, params):
        hc = httplib.HTTPConnection("xml.qrz.com")
        headers = {"Content-type": "application/x-www-form-urlencoded",
            "Accept": "text/plain"}
        hc.request("POST", "/xml", urllib.urlencode(params), headers)
        resp = hc.getresponse()
        if resp.status != httplib.OK:
            raise QrzRequestError("Status %d" % resp.status)
        return resp.read()


    def qrz(self, callsign):
        # http://xml.qrz.com/xml?s=2331uf894c4bd29f3923f3bacf02c532d7bd9;callsign=aa7bq
        log.debug("qrz %s" % callsign)
        miss = True
        c = self.db.cursor()
        xml = c.execute('select val from dict where key == ?',
                                                    (callsign,)).fetchone()
        if not xml:
            log.debug("miss %s" % callsign)
            xml = self.request(dict(s=self.key,callsign=callsign))
        else:
            log.debug("hit  %s" % callsign)
            miss = False
            xml = xml[0]
        try:
            dom = minidom.parseString(xml)
            session = Callsign(dom.getElementsByTagName("Session")[0])
            e = session['Error']
            if e:
                if not e.startswith("Not found"):
                    raise QrzError(e)
            if miss:
                self.db.execute("insert into dict values (?, ?)", (callsign, xml))
                self.db.commit();
            if e:
                raise NotFound(callsign)
            callnode = dom.getElementsByTagName("Callsign")[0]
            data = Callsign(callnode)
            if data['call'].lower() != callsign.lower():
                raise CallMismatch("Calls do not match", data['call'], callsign)
            return data
        except QrzError, e:
            log.warning("QRZ.com lookup failed: %s", repr(e))
            raise
        except Exception:
            log.debug(xml)
            raise

    def __enter__(self, *args, **kwargs):
        return self

    def __exit__(self, *args, **kwargs):
        self.db.close()


