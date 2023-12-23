========
Tutorial
========

This tutorial will guide you through setting up Blinken' Xmas on your Christmas
tree, with multiple strands of neopixels attached to the Pico, and a Raspberry
Pi with a camera module for the server to perform calibration on the positions.


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

* A `Pico W`_ or a Pico WH; note you need the WiFi capable variant (not the
  bare Pico), and that this project relies on the Pico's specific capabilities
  [#othermcu]_

* A `breadboard`_ large enough to mount your Pico and all associated wiring

* `Jumper leads`_ for the breadboard (or solid-core wire for those that like
  neatness!)

* A 5V power supply capable of driving the Pico (easy) and all your neopixels
  (harder); a typical micro-USB supply is *not* going to cut the mustard here
  but I'll go into more details below

* As many strands of WS2812 or APA102 compatible neopixels as you can
  reasonably fit on your tree; note these do not have to be the same model, RGB
  ordering, or length

* Whatever attachments you need to connect your neopixels to your Pico or the
  breadboard; if you're lucky your strands will already have breadboard
  compatible connectors attached, if not you may need to solder and/or crimp
  some on yourself

In this tutorial I'll be using an `63-line breadboard`_ with two separate power
rails which is probably overkill, but I don't like being cramped when wiring
things! For the neopixels, I'll be using 3× `50-LED strands of RGB WS2812
neopixels`_, and 1× 100-LED strand of GRB WS2812 neopixels because that's what
was lying around!


I have the Power!
=================

The power supply requires some consideration. The neopixels have a maximum
output power of 0.24W per LED (at 5V). All told I've got 250 LEDs, so that's a
total potential output of 250 × 0.24W = 60W, plus whatever's required for the
Pico but frankly that'll be so minimal by comparison it's not worth worrying
about!

At 5V that's 60W ÷ 5V = 12A which is *way* beyond the maximum output of the
typical micro-USB power supply used with Picos; these often top out at 1A or
2A.

We need something quite a bit bigger, and preferably with a decent amount of
overhead (it's rarely a good idea to run power supplies near their limits).
I'll be using an `5V 100W supply`_ which gives me 40W of head-room, but I'd
guesstimate that anything 80W+ should be sufficient.

.. image:: images/psu.*
    :align: center
    :alt: The power supply used in the tutorial. A large metal cuboid with
          several screw terminals at the rear (for mains input and 5V outputs)
          all surrounded by perforated aluminium for passive air cooling

.. warning::

    Please note that most of these supplies do not come with mains cables. You
    will need to be comfortable wiring your own mains cable to this (kids: get
    an adult to supervise)


Pi Setup
========

We'll start with the Pi side of things as that's relatively easy. I'll be using
`Ubuntu for the Raspberry Pi`_ rather than the more common RaspiOS mostly
because it's what I'm more familiar with [#job]_. More specifically, I'll be
using the 32-bit armhf variant because the legacy camera stack doesn't work on
arm64 [#raspios]_.

#. Insert your SD card into your computer, download `rpi-imager`_ (if you
   haven't got it already), and start it.

#. Select "CHOOSE DEVICE" and pick your model of Pi from the list (I'll be
   picking "Raspberry Pi 3" which includes the 3B+).

#. Select "CHOOSE OS", then "Other general-purpose OS", then "Ubuntu", then
   "Ubuntu Server 22.04.3 LTS (32-bit)".

#. Select "CHOOSE STORAGE", and pick your SD card from the list.

#. Select "NEXT", and follow the prompts to flash your SD card. Don't worry
   about customizing the first-time configuration because we're going to do
   some of that manually to have ``cloud-init`` handle all the installation.

Once the card is flashed, remove it from your computer, then re-insert it. You
should see the boot partition (named "system-boot") appear. Open this, and look
for the file named :file:`network-config`. Open this in your favoured text
editor and replace the contents with the following, changing the commented
values as appropriate:

.. code-block:: yaml

    network:
      version: 2
      wifis:
        wlan0:
          regulatory-domain: "GB"  # Replace with your country code
          dhcp4: true
          optional: true
          access-points:
            myhomewifi:            # Replace with your wifi SSID
              password: "S3kr1t"   # Replace with your wifi password

Next, open the :file:`user-data` file and replace the contents with the
following, changing the commented values as appropriate:

.. code-block:: yaml

    hostname: blinkenxmas

    keyboard:
      model: pc105
      layout: gb            # Replace with keyboard country (e.g. "us")

    ssh_pwauth: false
    ssh_import_id:
    - gh:waveform80         # Replace with gh:your-github-username

    apt:
      sources:
        blinkenxmas:
          source: "ppa:waveform/blinkenxmas"

    package_update: true
    package_upgrade: true

    packages:
    - avahi-daemon
    - blinkenxmas-server

Finally, open the :file:`config.txt` file and append the highlighted lines to
the end [#legacy]_:

.. TODO Add the rest of config.txt and highlight these lines

.. code-block:: conf

    [all]
    start_x=1
    gpu_mem=128

This should configure the Pi to connect to your WiFi network, import your SSH
keys from your GitHub username [#sshkeys]_, and install everything necessary on
the first boot. Speaking of which:

#. Eject the SD card from your computer, and insert it in your Pi

#. Connect the camera module to your Pi

#. Plug in your Pi and let it run through the first boot (this will take a
   while because of all the things we've asked ``cloud-init`` to handle)

I would advise having a monitor attached for the first boot just to make sure
everything works successfully, but if you're *really* confident this isn't
strictly necessary and after a little while you should be able to just SSH to
``ubuntu@blinkenxmas.local`` (the ``.local`` domain is because we're using
`Avahi's mDNS`_ to find the Pi regardless of its IP address).


Pico Setup
==========

Foo

----

.. _3B+: https://www.raspberrypi.com/products/raspberry-pi-3-model-b-plus/
.. _Pico W: https://www.raspberrypi.com/products/raspberry-pi-pico/
.. _breadboard: https://en.wikipedia.org/wiki/Breadboard
.. _63-line breadboard: https://shop.pimoroni.com/products/solderless-breadboard-830-point
.. _Jumper leads: https://shop.pimoroni.com/products/jumper-jerky
.. _50-LED strands of RGB WS2812 neopixels: https://shop.pimoroni.com/products/5m-flexible-rgb-led-wire-50-rgb-leds-aka-neopixel-ws2812-sk6812
.. _5V 100W supply: https://www.amazon.co.uk/Baiyouli-Universal-Regulated-Switching-10W-300W/dp/B07D6R2ZBK
.. _Ubuntu for the Raspberry Pi: https://ubuntu.com/raspberry-pi
.. _my job: https://waldorf.waveform.org.uk/pages/about.html
.. _rpi-imager: https://www.raspberrypi.com/software/
.. _Avahi's mDNS: https://en.wikipedia.org/wiki/Multicast_DNS

.. [#pi5] Note this set up has *not* been tested on a Raspberry Pi 5, on
   which the legacy camera stack does not work. The gstreamer camera stack
   *may* work on this model (in future I should add a libcamera based option).

.. [#v3] Note this has *not* been tested on a v3 camera module which is
   incompatible with the legacy camera stack. The gstreamer camera stack *may*
   work on this model (but again, I should add a libcamera based option).

.. [#webcam] Note that web-cams typically have *much* lower resolutions than
   Raspberry Pi camera modules, and higher resolutions are much better for
   calibration.

.. [#othermcu] This project won't work out of the box on other microcontrollers
   as it's using the Pico's PIOs to drive the neopixels. That said it's not
   hard to adjust the Pico's scripts (they're just MicroPython) so if anyone
   wants to try making it more generic, feel free!

.. [#job] It's `my job`_ after all!

.. [#raspios] If you want to try getting this working on RaspiOS, please do (it
   would be useful to add to this, or another, tutorial) but be aware you'll
   almost certainly have to use the gstreamer configuration (unless I get
   around to writing that libcamera backend …)

.. [#sshkeys] If you don't have this configured, you *can* comment out the
   ``ssh_import_id`` section and enable ``ssh_pwauth`` instead but I would
   strongly advise getting SSH keys configured on GitHub instead. It'll make
   things so much easier for you in future (and is much more secure)!

.. [#legacy] These options enable the legacy camera stack on the Pi. If you're
   going to be using gstreamer instead, skip this step.
