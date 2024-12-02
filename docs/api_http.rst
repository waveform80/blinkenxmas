================
blinkenxmas.http
================

.. module:: blinkenxmas.http

The :mod:`blinkenxmas.http` module defines classes for parsing HTTP requests
and constructing a response. This is a very basic implementation intended for
use with the standard library's :mod:`http.server`.

:class:`HTTPResponse`, in particular, accepts a wide variety of inputs
including file-like objects, :class:`pathlib.Path` instances, strings, or
byte-strings and will attempt to handle determination of encodings, content
types automatically. Furthermore, given the originating request, it will handle
cache and range-request response headers implicitly.

Several other functions are also provided for parsing HTTP Content- headers,
and MIME multipart form-data.


Classes
=======

.. autoclass:: DummyResponse

.. autoclass:: HTTPResponse

.. autoclass:: HTTPHeaders


Functions
=========

.. autofunction:: parse_content_value

.. autofunction:: split_multipart

.. autofunction:: parse_formdata
