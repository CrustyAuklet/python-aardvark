#!/usr/bin/env python

import nose
import pyaardvark
from nose.tools import ok_

def test_api_version():
    ok_(float(pyaardvark.api_version()) >= 5.3)

if __name__ == '__main__':
    nose.main()
