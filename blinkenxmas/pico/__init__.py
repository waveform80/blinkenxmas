# This file exists purely to permit the CPython code to access certain bits
# of the Pico logic, specifically the structures used to communicate data over
# MQTT. It is not copied to the Pico as part of the firmware.
#
# The following monkey-patch exists to paper over some of the differences
# between CPython and micropython. I *could* keep things like the packet format
# in a separate module which both micropython and CPython import without
# modification (or monkey-patching) but this takes more memory on the Pico.

import sys

class _MockModule:
    pass

class _MockMicropython:
    @staticmethod
    def const(s):
        return s

sys.modules['deflate'] = _MockModule()
sys.modules['micropython'] = _MockMicropython()
del _MockMicropython

from .animation import *
