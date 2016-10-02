#!/usr/bin/env python
"""
cty.dat file reader and lookup

Copyright 2014 by Jeffrey M. Laughlin
Copyright (C) 2005-2009 Fabian Kurz, DJ1YFK

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

Ported from yfklog

Alpha quality, largely untested; please help!
"""

from collections import defaultdict
import re

import pdb


class InvalidDxcc(Exception): pass
class InvalidCallsign(Exception): pass


class CtyDat(object):
    fields = ['name', 'cq', 'itu', 'cont', 'lat', 'lon', 'utcoff', 'prefix']

    def __init__(self, infile):
        self.prefixes = defaultdict(list)
        self.dxcc = {}
        for line in infile:
            if line[0] != ' ':
                # DXCC line
                line=line.strip()
                fields = [f.strip() for f in line.split(':')]
                dxcc = dict(zip(self.fields, fields))
                mainprefix = dxcc['prefix']
                self.dxcc[mainprefix] = dxcc
            else:
                line=line.strip()
                line = line.rstrip(';')
                line = line.rstrip(',')
                prefixes = line.split(',')
                self.prefixes[mainprefix].extend(prefixes)

    def getwpx(self, call):
        prefix = None
        a, b, c = None, None, None
        fields = re.split('/+', call)
        try:
            a, b, c = fields
        except Exception:
            try: a, b = fields
            except Exception:
                a = fields

        if c is None and None not in (a,b):
            if b in ('QRP', 'LGT'):
                b = a
                a = None

        if b.isdigit():
            raise InvalidCallsign(call)

        if a is None and c is None:
            if re.search('\d', b) is not None:
                prefix = re.search('(.+\d)[A-Z]*', b).group(0)
            else:
                prefix = b[0:2] + '0'
        elif a is None and c is not None:
            if len(c) == 1 and c.isdigit():
                _1 = re.search('(.+\d)[A-Z]*', b).group(0)
                mo = re.search('^([A-Z]\d)\d$', _1)
                if mo is not None:
                    prefix = _1 + c
                else:
                    mo = re.search('(.*[A-Z])\d+', _1)
                    prefix = mo.group(0) + c
            elif re.search('(^P$)|(^M{1,2}$)|(^AM$)|(^A$)', c) is not None:
                mo = re.search('(.+\d)[A-Z]*', b)
                prefix = mo.group(0)
            elif re.search('^\d\d+$/', c) is not None:
                mo = re.search('(.+\d)[A-Z]*', b)
                prefix = mo.group(0)
            else:
                if c[-1].isdigit():
                    prefix = c
                else:
                    prefix = c + '0'
        elif a is not None:
            if a[-1].isdigit():
                prefix = a
            else:
                prefix = a + '0'
        return prefix

    def getdxcc(self, call):
        matchchars = 0
        goodzone = None
        matchprefix = None
        if re.search('(^OH/)|(/OH[1-9]?$)', call) is not None:
            call = 'OH'
        elif re.search('(^3D2R)|(^3D2.+\/R)', call) is not None:
            call = '3D2RR'
        elif re.search('^3D2C', call) is not None:
            call = '3D2CR'
        elif '/' in call:
            prefix = self.getwpx(call)
            if prefix is None:
                prefix = 'QQ'
            call = prefix + 'AA'

        letter = call[0]
        for mainprefix, tests in self.prefixes.iteritems():
            for test in tests:
                testlen = len(test)
                if letter != test[0]:
                    continue
                zones = ''
                if testlen > 5 and '(' in test or '[' in test:
                    mo = re.search('^([A-Z0-9\/]+)([\[\(].+)', test)
                    if mo.group(1) is not None:
                        zones += mo.group(1)
                    testlen = len(mo.group(0))

                if call[:testlen] == test[:testlen] and matchchars <= testlen:
                    matchchars = testlen
                    matchprefix = mainprefix
                    goodzone = zones

        try:
            mydxcc = self.dxcc[matchprefix]
        except KeyError:
            raise InvalidDxcc(matchprefix)

        if goodzone is not None:
            mo = re.search('\((\d+)\)', goodzone)
            if mo is not None:
                mydxcc['cq'] = mo.group(0)
            mo = re.search('\[(\d+)\]', goodzone)
            if mo is not None:
                mydxcc['itu'] = mo.group(0)

        if mydxcc['prefix'].startswith('*'):
            if (mydxcc['prefix'] == '*TA1'):  mydxcc['prefix'] = "TA"  # Turkey
            if (mydxcc['prefix'] == '*4U1V'): mydxcc['prefix'] = "OE"  # 4U1VIC is in OE..
            if (mydxcc['prefix'] == '*GM/s'): mydxcc['prefix'] = "GM"  # Shetlands
            if (mydxcc['prefix'] == '*IG9'):  mydxcc['prefix'] = "I"  # African Italy
            if (mydxcc['prefix'] == '*IT9'):  mydxcc['prefix'] = "I"  # Sicily
            if (mydxcc['prefix'] == '*JW/b'): mydxcc['prefix'] = "JW"  # Bear Island

        return mydxcc

