================
blinkenxmas.conf
================

All applications in the Blinken' Xmas suite read their configuration from the
following locations:

* :file:`/usr/local/etc/blinkenxmas.conf`

* :file:`/etc/blinkenxmas.conf`

* :file:`{$XDG_CONFIG_HOME}/blinkenxmas.conf` where $XDG_CONFIG_HOME is
  typically :file:`~/.config`

If multiple of these exist, they are read in the order above with settings in
later files overriding settings from earlier ones. The configuration file
format is based on the common `INI file`_ format.

The following sections document the available settings.


[mqtt]
======

Configures the MQTT broker that :program:`bxweb` and :program:`bxcli` post to,
and to which the Pico will listen.

host
    The hostname of the MQTT broker. Even if the broker is present on the local
    machine, this must be set to a "proper" hostname, i.e. something other than
    "localhost". Default: "broker"

    This configuration is also used to generate the Pico's configuration, which
    will need the actual network address.

port
    The port on which the MQTT broker will be listening. May be specified as an
    integer or a registered service name. Default: 1833.

topic
    The topic to which the Pico should subscribe, and to which the web
    application will publish new animations for the tree to play.


[web]
=====

Settings specific to the :program:`bxweb` application.

bind
    The address to which :program:`bxweb` should bind and listen for
    connections. If you are running the application "bare" this should be set
    to "0.0.0.0" or "::" to bind to all interfaces. If you are using a reverse
    proxy, this should be set to "127.0.0.1" (the default) or "::1".

port
    The port on which :program:`bxweb` should listen for connections. If you
    are running the application "bare" this should be 80 (or 443 if you can be
    bothered to set up HTTPS for an xmas tree!). If you are running this behind
    a reverse proxy, this should be set to an unprivileged port like 8000 (the
    default).

database
    The path to the SQLite database used by :program:`bxweb` and
    :program:`bxcli` to store and retrieve preset animations, and tree LED
    coordinates.


[wifi]
======

Configures the wifi access point that the Pico connects to. Used by
:program:`bxflash` to generate the Pico's configuration.

ssid
    The SSID of the wifi access point that the Pico should attempt to connect
    to on startup.

password
    The password of the wifi access point that the Pico should use. Currently
    there is no support for anything other than basic PSK authentication.


[pico]
======

Configuration settings specific to the Pico. These are used by
:program:`bxflash` to generate the code uploaded to the Pico.

status
    The GPIO number (or name) of the status LED on the Pico. This is flashed
    in various patterns to indicate the current state. Defaults to "LED" which
    is the built-in LED on the Pico W.

error
    The action to take on a fatal error. May be set to "reset" (the default) to
    reboot the Pico, or "flash" to terminate and flash the status in a regular
    pattern. The "flash" setting is primarily intended for debugging as it
    permits connection to the serial console to query state.


[camera]
========

This section defines the camera used by :program:`bxweb` to calibrate the
positions of the LEDs on the tree.

type
    The type of camera available to the system running :program:`bxweb`. Can be
    set to one of:

    none
        No camera is available for tree calibration. The default.

    picamera
        Uses the legacy :mod:`picamera` library to control a Raspberry Pi
        camera module attached to the local system (which is presumably a
        Raspberry Pi)

    gstreamer
        Uses the GStreamer framework to query a V4L2 video source, typically a
        USB web-camera).

    files
        Uses a pre-captured set of JPEG images to emulate a camera. Primarily
        intended for development and testing purposes.

device
    When *type* is "gstreamer", the path of the V4L2 video source. Defaults to
    :file:`/dev/video0`

path
    When *type* is "files", the path of the pre-captured files. See
    :class:`blinkenxmas.cameras.FilesSource` for further details of the file
    naming convention expected.

capture
    The resolution at which to capture images, specified as a "WIDTHxHEIGHT"
    value, e.g. "1920x1080". For accuracy reasons, this should be set to the
    native capture resolution of the camera device, e.g. "2592x1944" for a v1
    Pi camera module.

preview
    The resolution at which to capture video for the web-based preview,
    specified as a "WIDTHxHEIGHT" value, e.g. "640x480". For performance
    reasons, this should generally be set to quite a low resolution.


[leds:\*]
=========

These sections define the various LED strips that are attached to the tree. At
least 1, and up to 8 of these sections may be defined. The "*" in the section
title is arbitrary and simply used to distinguish the sections.

driver
    Set to either "WS2812" or "APA102" depending on the sort of neopixels
    present in the strip.

pin
    When *driver* is "WS2812", specifies the GPIO pin connected to the data pin
    of the neopixels in the strip.

dat, clk
    When *driver* is "APA102", specifies the GPIO pins connected to the DAT
    (data) and CLK (clock) pins of the neopixels in the strip, respectively.

count
    The number of neopixels in the strip. Typically some multiple of 50.

order
    Specifies the color ordering expected by the neopixels in the strip.
    Usually "RGB" or "GRB", but any combination of R, G, and B is accepted,
    e.g. "BGR". If the neopixels include a separate white channel, append "W"
    to the value, e.g. "RGBW" or "GRBW".

fps
    The maximum refresh rate to apply to the neopixels in the strip. Defaults
    to 60.

    .. note::

        Dropping this to 30 can considerably speed up tranmission of animations
        as it halves the amount of data involved, but with obvious implications
        for the smoothness of animation.

reversed
    If "no" (the default), the neopixels are addressed from the "start" of the
    strip; if "yes", from the end.

    This is primarily useful in non-calibrated installations where you are
    relying on the position along the strip for certain effects, have multiple
    strips, and want one strip to "continue" an animation from the top of the
    tree (the end of another strip) back to the bottom.


Example
=======

.. literalinclude:: ../blinkenxmas/default.conf
    :language: ini
    :caption: /etc/blinkenxmas.conf

.. _INI file: https://en.wikipedia.org/wiki/INI_file
