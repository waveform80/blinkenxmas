========
Tutorial
========

This tutorial will guide you through setting up Blinken' Xmas on your Christmas
tree, with multiple strands of neopixels attached to the Pico, and a Raspberry
Pi with a camera module for the server to perform calibration on the positions.


Skills List
===========

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

* Editing a text configuration file from the Linux command line. Or at very
  least being able to scp it off to a machine where you edit it and scp it
  back, but given that there'll be some user switching involved you are *much*
  better off just being able to edit things at the command line


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

* A `breadboard`_, `stripboard`_, or protoboard large enough to mount your Pico
  and all associated wiring

* `Jumper leads`_ (breadboards only) or solid-core wire (all board types)

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

In this tutorial I'll be using an `63-line breadboard`_ with two separate power
rails which is probably overkill, but I don't like being cramped when wiring
things! For the neopixels, I'll be using a `50-LED strands of RGB WS2812
neopixels`_, and a 100-LED strand of GRB WS2812 neopixels because that's what
was lying around!


I have the Power!
=================

The power supply requires some consideration. The neopixels have a maximum
output power of 0.24W per LED (at 5V). All told I've got 150 LEDs, so that's a
total potential output of 150 × 0.24W = 36W, plus whatever's required for the
Pico but frankly that'll be so minimal by comparison it's not worth worrying
about!

At 5V that's 36W ÷ 5V = 7.2A which is *way* beyond the maximum output of the
typical micro-USB power supply used with Picos; these often top out at 1A or
2A.

We need something quite a bit bigger, and preferably with a decent amount of
overhead (it's rarely a good idea to run power supplies near their limits).
I'll be using an `5V 100W supply`_ which gives me 64W of head-room, but I'd
guesstimate that anything 50W+ should be sufficient.

.. image:: images/psu.*
    :align: center
    :alt: The power supply used in the tutorial. A large metal cuboid with
          several screw terminals at the rear (for mains input and 5V outputs)
          all surrounded by perforated aluminium for passive air cooling

.. warning::

    Please note that most of these supplies do not come with mains cables. This
    is why I included being comfortable with wiring mains cables to a power
    supply in the skills list at the top. You will need to be confident that
    you know which leads are live, neutral, and ground, when wiring this thing
    up.

Another thing to consider is heat in your wiring. The mains leads should be
fine. At 240V, 100W is barely anything in amps: 100W ÷ 240V = 0.24A. However,
consider the 5V side of things.

We've already calculated we'll be pushing 7.2A through our wiring. Now the
individual LED strips themselves will only be taking what they need, so the
100-LED strip will take 4.8A (⅔ of 7.2A) and the 50-LED strip will take 2.4A (⅓
of 7.2A). However, the 5V wire running from the power supply will be carrying
the full 7.2A. With typical 24AWG solid-core wire that's okay.

But let me caution you on the hazards of scaling this up without thinking about
this! The first year I got this working, I used 150 LEDs, as we are in this
tutorial. The next year, I scaled it up to 250 LEDs thinking "there's more than
enough headroom in the power supply", but not considering the heating situation
on the 5V side of things. 250 × 0.24W = 60W. 60W ÷ 5V = 12A. Pushing 12A
through 24AWG cable causes things to get *hot*:

.. image:: images/el_scorchio.*
    :align: center
    :alt: A picture of the breadboard containing the Pico W and various linking
          various rows. Notably, one hole of the bottom positive rail is
          discoloured and clearly partially melted.

You can clearly see where I'd connected 5V from the power supply to the
breadboard … it's that melted hole on the bottom positive rail! I only noticed
this after taking everything apart after the holidays, and then realized (given
all this was housed rather carelessly in a spare cardboard box) just how close
I'd come to setting fire to the tree!

The moral of the story is: if you're planning to scale this beyond 150 LEDs,
please take the time to calculate how much ampage you're going to push through
your 5V wiring. If necessary, split the load across multiple supplies (most of
these supplies have multiple outputs), or get thicker gauge wire. And maybe
housing all this in a non-flammable box!


Pi Setup
========

We'll start with the Pi side of things as that's relatively easy. I'll be using
`Ubuntu for the Raspberry Pi`_ rather than the more common RaspiOS mostly
because it's what I'm more familiar with [#job]_. More specifically, I'll be
using the 32-bit armhf variant of 22.04 because the legacy camera stack doesn't
work on arm64 [#raspios]_ or on the later versions of Ubuntu.

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
          optional: false
          access-points:
            myhomewifi:            # Replace with your wifi SSID
              password: "S3kr1t"   # Replace with your wifi password

Next, open the :file:`user-data` file and replace the contents with the
following, changing the commented values as appropriate:

.. code-block:: yaml

    hostname: blinkenxmas

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

.. code-block:: ini
    :emphasize-lines: 43-44

    [all]
    kernel=vmlinuz
    cmdline=cmdline.txt
    initramfs initrd.img followkernel

    [pi4]
    max_framebuffers=2
    arm_boost=1

    [all]
    # Enable the audio output, I2C and SPI interfaces on the GPIO header. As these
    # parameters related to the base device-tree they must appear *before* any
    # other dtoverlay= specification
    dtparam=audio=on
    dtparam=i2c_arm=on
    dtparam=spi=on

    # Comment out the following line if the edges of the desktop appear outside
    # the edges of your display
    disable_overscan=1

    # If you have issues with audio, you may try uncommenting the following line
    # which forces the HDMI output into HDMI mode instead of DVI (which doesn't
    # support audio output)
    #hdmi_drive=2

    # Enable the serial pins
    enable_uart=1

    # Autoload overlays for any recognized cameras or displays that are attached
    # to the CSI/DSI ports. Please note this is for libcamera support, *not* for
    # the legacy camera stack
    camera_auto_detect=1
    display_auto_detect=1


    [cm4]
    # Enable the USB2 outputs on the IO board (assuming your CM4 is plugged into
    # such a board)
    dtoverlay=dwc2,dr_mode=host

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

As on the Pi, the first thing to do with the Pico is get some software onto it.

.. warning::

    You are about to erase everything on your Pico W. If you've got any code
    saved on there that you want to preserve, take a copy of it first.

The first thing to load is a special MicroPython build which includes
Pimoroni's fabulous "plasma" library. One of the following should suffice,
depending on your model of Pico:

2040-based Pico W
    `pimoroni-pico releases`_

2350-based Pico 2W
    `pimoroni-pico-rp2350 releases`_

For reference, I've used pimoroni-pico 1.21.0 on a Pico W, and
pimoroni-pico-rp2350 0.0.10 on a `Pico Plus 2W`_, but you should probably just
grab the latest build for your specific board. The file should have a name
something like :file:`{board}-{version}-pimoroni-micropython.uf2`.

Find a cable suitable for connecting your Pico to your computer, but don't
connect it just yet! Plug one end of the cable into your computer, then hold
down the "BOOTSEL" button on the Pico while inserting the other end of the
cable into the Pico. Continue holding the button for about a second after
you've inserted the cable. This procedure puts the Pico into a mode where you
can re-flash it.

Shortly after, you should see the drive "RPI-RP2" appear. Copy the
pimoroni-pico firmware you downloaded (the
:file:`{board}-{version}-pimoroni-micropython.uf2` file) to this drive. It
should take a few seconds to copy, then a brief time later you should see the
drive disappear again. This indicates the Pico has accepted the firmware and
has rebooted into MicroPython.


Pico, meet Pi!
==============

Unplug the Pico W from your computer, and plug it into your Raspberry Pi.

----

.. _3B+: https://www.raspberrypi.com/products/raspberry-pi-3-model-b-plus/
.. _Pico W: https://www.raspberrypi.com/products/raspberry-pi-pico/
.. _Pico 2W: https://www.raspberrypi.com/products/raspberry-pi-pico-2/
.. _Pico Plus 2W: https://shop.pimoroni.com/products/pimoroni-pico-plus-2-w
.. _breadboard: https://en.wikipedia.org/wiki/Breadboard
.. _stripboard: https://en.wikipedia.org/wiki/Stripboard
.. _63-line breadboard: https://shop.pimoroni.com/products/solderless-breadboard-830-point
.. _Jumper leads: https://shop.pimoroni.com/products/jumper-jerky
.. _50-LED strands of RGB WS2812 neopixels: https://shop.pimoroni.com/products/5m-flexible-rgb-led-wire-50-rgb-leds-aka-neopixel-ws2812-sk6812
.. _5V 100W supply: https://www.amazon.co.uk/Baiyouli-Universal-Regulated-Switching-10W-300W/dp/B07D6R2ZBK
.. _Ubuntu for the Raspberry Pi: https://ubuntu.com/raspberry-pi
.. _my job: https://waldorf.waveform.org.uk/pages/about.html
.. _rpi-imager: https://www.raspberrypi.com/software/
.. _Avahi's mDNS: https://en.wikipedia.org/wiki/Multicast_DNS
.. _pimoroni-pico releases: https://github.com/pimoroni/pimoroni-pico/releases
.. _pimoroni-pico-rp2350 releases: https://github.com/pimoroni/pimoroni-pico-rp2350/releases

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
