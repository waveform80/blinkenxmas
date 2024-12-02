=================
blinkenxmas.httpd
=================

.. module:: blinkenxmas.httpd

The :mod:`blinkenxmas.httpd` module extends the standard library's
:mod:`http.server` with handling functions for form-data, JSON content, and a
mechanism to route requests to static content, :mod:`chameleon` generated
content, or dynamic functions.

It also defines the :class:`HTTPThread` class, the main thread used by the
:program:`bxweb` application to service HTTP clients, the :func:`route`
decorator used to associate handler functions with their HTTP virtual path (see
:mod:`blinkenxmas.routes`), and the :func:`animation` decorator used to declare
LED animation generators for the main interface.


HTTP handlers
=============

.. autofunction:: route

.. autoclass:: HTTPServer

.. autoclass:: HTTPRequestHandler

.. autoclass:: HTTPThread


Animation handlers
==================

.. autofunction:: animation

.. autoclass:: Function

.. autoclass:: Param

.. autoclass:: ParamLEDCount

.. autoclass:: ParamLEDPositions

.. autoclass:: ParamFPS


Support functions
=================

.. autofunction:: get_best_family

.. autofunction:: for_commands

.. autoclass:: Messages
