#!/usr/bin/env python
"""
ESPN Fantasy Baseball Table Parser
========================

"""
#    Copyright (C) 2015-2016 by
#    S. Brian Huey (sbhuey@gmail.com)
#    All rights reserved.
#
#
import sys
if sys.version_info[:2] < (2, 7):
    m = "Python 2.7 or later is required for PyVISSIM (%d.%d detected)."
    raise ImportError(m % sys.version_info[:2])
del sys
from espn_tables import *
