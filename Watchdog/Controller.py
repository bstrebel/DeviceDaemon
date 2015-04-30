#!/usr/bin/env python

"""
    Watchdog Controller
    check devices by bluetooth address or hostname

"""
__version__ = "0.1"
__author__ = 'bst'

import bluetooth
import select
import re

from BluetoothDevice import *
from PingDevice import *

class Controller(object):




