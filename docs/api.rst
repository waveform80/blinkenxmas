=============
API Reference
=============

.. module:: blinkenxmas

The Blinken' Xmas code tries to be as reasonably self-contained as possible, to
avoid too many dependencies in order to make the packaging a bit easier and
low-maintenance longevity a bit more likely.

The following sections list the various modules in the Python code:

.. toctree::
    :maxdepth: 1

    api_animations
    api_calibrate
    api_cameras
    api_cli
    api_compat
    api_config
    api_flash
    api_http
    api_httpd
    api_mqtt
    api_routes
    api_store
    api_web

I'm afraid the Pico-side code is (currently) largely undocumented. However, it
is much simpler, and if you can understand the Pi-side of the code you'll
easily handle the Pico side.
