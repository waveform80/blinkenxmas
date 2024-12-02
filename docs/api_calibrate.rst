=====================
blinkenxmas.calibrate
=====================

.. module:: blinkenxmas.calibrate

The :mod:`blinkenxmas.calibrate` module defines the classes associated with
calculating the 3D position of LEDs on the tree. The first phase consists of
:class:`AngleScanner`, which uses the camera to capture images of the tree. A
base "unlit" image is capture, then images with each LED lit in turn. The
scanner then uses some simple image manipulations (masking, gaussian blur, and
saturated subtractions) to determine the likely 2D position of each LED for the
particular angle of the tree.

In the second phase, :class:`PositionsCalculator` takes the 2D positions and
the angles they were captured at. It uses some simple trigonometry to calculate
the likely 3D position of each LED, trying to eliminate bad estimations using
derived "scores".

.. warning::

    At present, much of this module is undocumented as it's the result of
    several late nights, dredging up long bit-rotted trigonometric knowledge,
    querying StackExchange, and random experimentation. It's by far the most
    interesting module in the project, but equally I can only apologize to
    anyone trying to understand it!

Classes
=======

.. autoclass:: AngleScanner

.. autoclass:: PositionsCalculator

.. autoclass:: Calibration

Exceptions
==========

.. autoexception:: PointNotFound

Utility functions
=================

.. autofunction:: weighted_median
