#!/usr/bin/env python

from distutils.core import setup

setup(
    name='hamtools',
    version='0.1',
    description='N1YWB Python Ham Tools',
    author='Jeff Laughlin',
    author_email='n1ywb@arrl.net',
    url='https://github.com/n1ywb/python-hamtools',
    py_modules = ['hamtools'],
    scripts = ['geolog', 'vk'],
    install_requires = ['geojson'],
    long_description = (
"""Collection of amateur radio tools. Includes ability to read ADIF and
Cabrillo log files, cty.dat files, georeference callsigns via QRZ.com and
cty.dat, and output GIS data in GeoJSON and KML formats.""")
)

