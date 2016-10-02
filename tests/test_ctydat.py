#!/usr/bin/env python
"""Describe file"""
from hamtools.ctydat import CtyDat
from pkg_resources import resource_stream
import pytest

call = 'SW8/SW1KYQ//P'

@pytest.fixture('session')
def ctydat():
    ctydatflo = resource_stream('hamtools', "ctydat/cty.dat")
    ctydat = CtyDat(ctydatflo)
    return ctydat


def test_getwpx(ctydat):
    assert ctydat.getwpx(call) == 'SW8'

