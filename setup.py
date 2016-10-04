#!/usr/bin/env python

from setuptools import setup

setup(
    name='hamtools',
    version='0.3',
    description='N1YWB Python Ham Radio Tools',
    author='Jeff Laughlin',
    author_email='jeff@jefflaughlinconsulting.com',
    url='https://github.com/n1ywb/python-hamtools',
    download_url='https://github.com/n1ywb/python-hamtools/archive/0.3.zip',
    packages = ['hamtools'],
    package_data={'hamtools': ['ctydat/cty.dat']},
    scripts = ['geolog', 'vk'],
    install_requires = ['geojson', 'requests', 'requests-cache'],
    keywords = ['ham', 'amateur', 'qrz', 'adif', 'cabrillo', 'kml', 'geojson', 'ctydat'],
    long_description = (
"""Collection of amateur radio tools. Includes ability to read ADIF and
Cabrillo log files, cty.dat files, georeference callsigns via QRZ.com,
callook, and ctydat, and output GIS data in GeoJSON and KML formats.""")
)
