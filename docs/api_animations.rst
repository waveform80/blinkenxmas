======================
blinkenxmas.animations
======================

.. module:: blinkenxmas.animations

The :mod:`blinkenxmas.animations` module defines the animation functions
available for generating presets. Specifically, any function decorated with the
:func:`~blinkenxmas.httpd.animation` decorator is registered as an available
animation in the interface.

Animation functions can take an arbitrary set of
parameters. The decorator's parameters affect how the parameters of the
function will be rendered in the interface. For this reason, you are encouraged
to look at the full definition of each animation function *including its
decorator*. The function must return a :class:`list` of :class:`list` of
:class:`~colorzero.Color`. The outer list defines the "frames" of the
animation. Each inner list defines the color of each LED in index order.

For example, here is the full definition of :func:`gradient_by_index`:

.. code-block:: python3

    @animation('Gradient (by index)',
               led_count=ParamLEDCount(),
               color1=Param('From', 'color', default='#000000'),
               color2=Param('To', 'color', default='#ffffff'))
    def gradient_by_index(led_count, color1, color2):
        gradient = color1.gradient(color2, steps=led_count)
        return [[color for color in gradient]]

The decorator defines the title for the animation, and the label, type, and
defaults for each parameter. The result is a list of lists, but as there's only
one "frame" the outer list contains one item.


Animation functions
===================

.. autofunction:: one_color

.. autofunction:: gradient_by_index

.. autofunction:: gradient_by_pos

.. autofunction:: sweep_by_index

.. autofunction:: sweep_by_pos

.. autofunction:: flash

.. autofunction:: twinkle

.. autofunction:: rainbow_by_index

.. autofunction:: rainbow_by_pos

.. autofunction:: scrolling_rainbow_by_index

.. autofunction:: spinning_rainbow

.. autofunction:: pride_flags


Utility functions
=================

.. autofunction:: scale

.. autofunction:: range_of

.. autofunction:: pairwise

.. autofunction:: preview
