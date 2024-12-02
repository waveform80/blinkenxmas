.. program:: bxweb

=====
bxweb
=====

The HTTP server for the Blinken' Xmas project. Provides a simple web-interface
for building tree animations and serving them over MQTT to the Pico connected
to the neopixels on the tree.


Synopsis
========

::

    bxweb [-h] [--version] [--broker-address ADDR] [--broker-port NUM]
          [--topic TOPIC] [--httpd-bind ADDR] [--httpd-port PORT]
          [--no-production] [--production] [--db FILE]


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

    The topic on which the Pico W is listening for messages. Default:
    blinkenxmas

.. option:: --httpd-bind ADDR

    The address on which to listen for HTTP requests. Default: 0.0.0.0

.. option:: --httpd-port PORT

    The port to listen for HTTP requests. Default: 8000

.. option:: --no-production, --production

    If specified, run in production mode where an internal server error will
    not terminate the server and will not output a stack trace (default: no)

.. option:: --db FILE

    The SQLite database to store presets in. Default:
    :file:`/var/local/cache/blinkenxmas/presets.db`


Configuration
=============

This application is a basic no-frills HTTP server producing the web front-end.
While it is multi-threaded, it isn't intended to scale to large numbers of
users, because there's no need with a single tree! Moreover, there's no
authentication, and no assumptions should be made as to the application's
security. To run this on the standard port 80 (or 443), you are recommended to
place the application on an unprivileged port (e.g. the default of 8000),
running as an unprivileged user, and place a reverse proxy (like nginx) in
front of it.

A sample :manpage:`systemd.unit(5)` for execution of the application is:

.. literalinclude:: ../blinkenxmas-web.service
    :language: systemd
    :caption: /etc/systemd/system/blinkenxmas-web.service

.. note::

    At the time of writing, the application does not support systemd's
    notify mechanism, or socket activation.

A sample reverse proxy for nginx is:

.. literalinclude:: ../blinkenxmas.nginx
    :language: nginx
    :caption: /etc/nginx/sites-available/blinkenxmas


Environment
===========

.. envvar:: DEBUG

    If set to "1", the application will produce a full stack-trace on any
    fatal exception. If set to "2", the application will jump to PDB for
    exception post-mortem on any fatal exception.


See Also
========

:doc:`bxcli`, :doc:`bxflash`, :doc:`blinkenxmas.conf`
