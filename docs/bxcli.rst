.. program:: bxcli

=====
bxcli
=====

The command line interface for the Blinken' Xmas project. Provides a simple
command line which can load or delete an existing preset, set all LEDs to a
specific color, or set an individual LED to a specified color.


Synopsis
========

::

    bxcli [-h] [--version] [--broker-address ADDR] [--broker-port NUM]
          [--topic TOPIC] {command} ...


Options
=======

.. option:: -h, --help

    Show the help message and exit

.. option:: --version

    Show program's version number and exit

.. option:: --broker-address ADDR

    The address on which to find the MQTT broker. Default: broker

.. option:: --broker-port NUM

    The port on which to find the MQTT broker. Default: 1883

.. option:: --topic TOPIC

    The topic on which the Pico W is listening for messages. Default: blinkenxmas

.. option:: command

    See `Commands`_ below


Commands
========

help [command]
    Display help on the specified *command*, or a summary of all commands

off
    Switch all LEDs off

on {color}
    Switch all LEDs on with the specified *color*, given as a common CSS3 color
    name, or an HTML color code in the form #RRGGBB, e.g. #FF0000 for red.

set {index} {color}
    Set LED *index* to the specified *color*. The *index* is simply an integer
    number counting from 0..n-1 where *n* is the total number of LEDs present
    in the tree. The *color* is given as a common CSS3 color name, or an HTML
    color code in the form #RRGGBB.

list
    Display the names of all presets currently stored in the database on the
    terminal.

show {preset}
    Display the specified *preset* on the tree. Note that preset names
    containing special characters or spaces will likely need quoting on the
    command line.


Debugging
=========

The **on** command is particular useful for testing your setup. To ensure your
power setup is adequate (and adequately isolated), try:

.. code-block:: console

    $ bxcli on "#ffffff"

This should switch all LEDs on at full white (shield your eyes!). If your Pico
crashes, you are likely using a single supply (or single rail on a single
supply) for both your LEDs and the Pico. This is likely to fail when there are
sudden fluctuations in the brightness of the LEDs, leading to brief voltage
drops on the line.

Assuming everything does light correctly, and the Pico doesn't crash, leave the
tree fully lit for a minute, and check the heat of the cables running from your
power supply to the neopixels. If they are too hot to touch, you are strongly
advised to replace those cables with something thicker.


See Also
========

:doc:`bxweb`, :doc:`bxflash`, :doc:`blinkenxmas.conf`
