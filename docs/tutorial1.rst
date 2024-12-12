Requirements
============

You will need to be comfortable doing the following:

* Soldering, unless you buy a Pico WH with the headers pre-soldered

* Crimping, unless all your LED strips have connectors suitable for a
  breadboard pre-crimped onto them

* Wiring a mains power lead to a power supply; this just means some wire in
  some screw terminals, but you need to be confident you know which wires are
  live, neutral, and ground. If you're not confident (and/or competent!) in
  this, *please* get help from someone who is.

* SSH'ing to a Linux command line, *preferably* using pub-key authentication

* Running commands at a Linux command line

* Editing a text configuration file from the Linux command line using nano,
  vim, or your favourite console text editor (you can try copying stuff back
  and forth, but given there'll be some user switching involved you are *much*
  better off just being able to edit things at the command line)


Shopping List
=============

You'll need the following bits of hardware to follow this tutorial. Don't worry
if you have fewer neopixels, or a slightly different model of Pi. Hints on
adjusting the instructions to other configurations will be included along the
way:

* A Christmas tree

* A WiFi capable network

* A Raspberry Pi; I'm using a `3B+`_ but any model [#pi5]_ with a CSI camera
  port should work

* A camera for your Pi; I'm using an old v1 camera module, but you can use
  later models [#v3]_ too or even a web-cam [#webcam]_

* An SD card for your Pi; I'm using a spare 32GB SanDisk Ultra card

* A power supply for your Pi; micro-USB for models older than the 4B, USB-C for
  the 4B or later

* A `Pico W`_, or some variant thereof (including a `Pico 2W`_, `Pico Plus
  2W`_, etc.); note you need a WiFi capable variant (not the bare Pico), and
  that this project relies on the Pico's specific capabilities [#othermcu]_

* A `breadboard`_ large enough to mount your Pico and all associated wiring

* A momentary push-button suitable for mounting on a breadboard

* A red LED

* A 330Ω resistor

* `Jumper leads`_ or solid-core wire

* A 5V power supply capable of driving the Pico (easy) and all your neopixels
  (harder); a typical micro-USB supply is *not* going to cut the mustard here
  but I'll go into more details below

* As many strands of WS2812 or APA102 compatible neopixels as you can
  reasonably fit on your tree; note these do not have to be the same model, RGB
  ordering, or length

* Whatever attachments you need to connect your neopixels to your Pico or your
  carrier board; if you're lucky your strands will already have compatible
  connectors attached, if not you may need to solder and/or crimp some on
  yourself

* A box made of a non-flammable material large enough to house the power
  supply, breadboard, and all associated wiring

* Some cable glands large enough to accommodate at least the mains cable

In this tutorial I'll be using an `63-line breadboard`_ with two separate power
rails which is probably overkill, but I don't like being cramped when wiring
things! For the neopixels, I'll be using a `50-LED strand of RGB WS2812
neopixels`_, and a 100-LED strand of GRB WS2812 neopixels because that's what
was lying around.

.. _3B+: https://www.raspberrypi.com/products/raspberry-pi-3-model-b-plus/
.. _Pico W: https://www.raspberrypi.com/products/raspberry-pi-pico/
.. _Pico 2W: https://www.raspberrypi.com/products/raspberry-pi-pico-2/
.. _Pico Plus 2W: https://shop.pimoroni.com/products/pimoroni-pico-plus-2-w
.. _breadboard: https://en.wikipedia.org/wiki/Breadboard
.. _63-line breadboard: https://shop.pimoroni.com/products/solderless-breadboard-830-point
.. _Jumper leads: https://shop.pimoroni.com/products/jumper-jerky
.. _50-LED strand of RGB WS2812 neopixels: https://shop.pimoroni.com/products/5m-flexible-rgb-led-wire-50-rgb-leds-aka-neopixel-ws2812-sk6812

----

.. [#pi5] Note this set up has *not* been tested on a Raspberry Pi 5, on
   which the legacy camera stack does not work. The gstreamer camera stack
   *may* work on this model (in future I should add a libcamera based option).

.. [#v3] Note this has *not* been tested on a v3 camera module which is
   incompatible with the legacy camera stack. The gstreamer camera stack *may*
   work on this model (but again, I should add a libcamera based option).

.. [#webcam] Note that web-cams typically have *much* lower resolutions than
   Raspberry Pi camera modules, and higher resolutions are better for
   calibration.

.. [#othermcu] This project won't work out of the box on other microcontrollers
   as it's using the Pico's PIOs to drive the neopixels. That said it's not
   hard to adjust the Pico's scripts (they're just MicroPython) so if anyone
   wants to try making it more generic, feel free!
