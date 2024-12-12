========
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
    :emphasize-lines: 5,9-10

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
    :emphasize-lines: 5

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

Finally, open the :file:`config.txt` file, comment out the camera and display
auto-detect lines, and append the highlighted lines to the end to enable the
legacy camera stack [#legacy]_:

.. code-block:: ini
    :emphasize-lines: 33-34,42-43

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
    #camera_auto_detect=1
    #display_auto_detect=1

    [cm4]
    # Enable the USB2 outputs on the IO board (assuming your CM4 is plugged into
    # such a board)
    dtoverlay=dwc2,dr_mode=host

    [all]
    start_x=1
    gpu_mem=128

This should configure the Pi to connect to your WiFi network, import your SSH
keys from your GitHub username [#sshkeys]_, and install everything necessary on
the first boot. Speaking of which...


First boot
==========

#. Eject the SD card from your computer, and insert it in your Pi

#. Connect the camera module to your Pi

#. Plug in your Pi and let it run through the first boot (this will take a
   while because of all the things we've asked ``cloud-init`` to handle)

I would advise having a monitor attached for the first boot just to make sure
everything works successfully, but if you're *really* confident this isn't
strictly necessary and after a little while you should be able to just SSH to
``ubuntu@blinkenxmas.local`` (the ``.local`` domain is because we're using
`Avahi's mDNS`_ to find the Pi regardless of its IP address).


Finishing touches
=================

All the necessary software should have been installed by cloud-init, so all
that remains is for us to reconfigure things a little. Edit the
:file:`/etc/blinkenxmas.conf` file changing the highlighted lines below
(comments have been excluded for brevity):

.. code-block:: ini
    :emphasize-lines: 2,12-13,16,20-23,25-37

    [mqtt]
    host = blinkenxmas
    port = 1883
    topic = blinkenxmas

    [web]
    bind = 127.0.0.1
    port = 8000
    database = /var/cache/blinkenxmas/presets.db

    [wifi]
    ssid = your-ssid-here
    password = your-wifi-password-here

    [pico]
    status = 22
    error = reset

    [camera]
    type = picamera
    capture = 2592x1944
    preview = 640x480
    rotate = 0

    [leds:1]
    driver = WS2812
    count = 50
    fps = 60
    order = RGB
    pin = 15

    [leds:2]
    driver = WS2812
    count = 100
    fps = 60
    order = GRB
    pin = 16

.. note::

    The file is owned by root, so you will need to use :manpage:`sudo(1)` with
    your editor.

With the file updated, we need to add the ``blinkenxmas`` user to the ``video``
group so that it can access the Pi's camera, set the ``blinkenxmas`` site to be
nginx's default, and restart the ``blinkenxmas-server`` service:

.. code-block:: console

    $ sudo adduser blinkenxmas video
    $ cd /etc/nginx/sites-enabled
    $ sudo ln -sf ../sites-available/blinkenxmas default
    $ sudo systemctl restart blinkenxmas-server.service


.. _Ubuntu for the Raspberry Pi: https://ubuntu.com/raspberry-pi
.. _my job: https://waldorf.waveform.org.uk/pages/about.html
.. _rpi-imager: https://www.raspberrypi.com/software/
.. _Avahi's mDNS: https://en.wikipedia.org/wiki/Multicast_DNS

----

.. [#job] It's `my job`_ after all!

.. [#raspios] If you want to try getting this working on RaspiOS, please do (it
   would be useful to add to this, or another, tutorial) but be aware you'll
   almost certainly have to use the gstreamer configuration (unless I get
   around to writing that libcamera backend …)

.. [#legacy] These options enable the legacy camera stack on the Pi. If you're
   going to be using gstreamer instead, skip this step.

.. [#sshkeys] If you don't have this configured, you *can* comment out the
   ``ssh_import_id`` section and enable ``ssh_pwauth`` instead but I would
   strongly advise getting SSH keys configured on GitHub instead. It'll make
   things so much easier for you in future (and is much more secure)!
