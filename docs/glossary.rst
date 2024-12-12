===========
Glossary
===========


.. glossary::

    AWG
        `American Wire Gauge
        <https://en.wikipedia.org/wiki/American_wire_gauge>`_; a typically
        American measurement of conductive wire sizes.

    CPU
        `Central Processing Unit
        <https://en.wikipedia.org/wiki/Central_processing_unit>`_; the "brain"
        of a computer.

    CSI
        `Camera Serial Interface
        <https://en.wikipedia.org/wiki/Camera_Serial_Interface>`_; a standard
        interface for cameras in mobile or embedded systems. Notably the
        interface used by all Raspberry Pi models to connect camera modules (in
        various form factors).

    GPIO
        `General Purpose Input/Output
        <https://en.wikipedia.org/wiki/General-purpose_input/output>`_; in the
        context of :term:`SBCs <SBC>`, this typically refers to the prominent
        pin-header (often containing 2×20 pins) along one edge of the board.
        Some (but not all) of these pins may be controlled by software,
        operating as inputs or outputs.

    I²C
        The `Inter-Integrated Circuit
        <https://en.wikipedia.org/wiki/I%C2%B2C>`_ interface. A low-speed
        peripheral bus capable of connecting multiple peripherals sharing the
        same two wires for communication. Typically runs at a bandwidth of
        100Kbits/s. Commonly found exposed on the :term:`GPIO` headers of many
        :term:`SBCs <SBC>`.

    LED
        `Light Emitting Diode
        <https://en.wikipedia.org/wiki/Light-emitting_diode>`_. As the name
        suggests, a diode which emits light when conducating in the "forward"
        direction. The basic building block of a :term:`neopixel`.


        which
        typically contains three (or sometimes four) LEDs, one red, one green,
        one blue, and optionally one white (which typically provides better
        spectral output than the red, green, blue combination).

    neopixel
        A compound :term:`LED` typically consisting of red, green, blue, and
        optionally white LEDs which can be varied in intensity individually to
        produce any visible color. Comes in two major variants: WS2812 which
        uses a single :term:`PWM` data channel, and APA102 which is based upon
        the pre-existing :term:`I²C` protocol

    OS
        `Operating System <https://en.wikipedia.org/wiki/Operating_system>`_

    Pico
        Raspberry Pi's brand of micro-controller. Currently based on either the
        RP2040 or RP2350 chips, the major feature of the Pico (which Blinken'
        Xmas relies upon) is the :term:`PIO` state machines that enable it to
        control many neopixels without :term:`CPU` load.

    PIO
        `Programmable I/O
        <https://hackspace.raspberrypi.com/articles/what-is-programmable-i-o-on-raspberry-pi-pico>`_;
        the "unique" feature of the Raspberry Pi Pico which offloads
        :term:`GPIO` processing to one of several independent units that can
        read input or write output to GPIO pins without :term:`CPU`
        intervention (or load).

    PWM
        `Pulse Width Modulation
        <https://en.wikipedia.org/wiki/Pulse-width_modulation>`_; a technique
        of transmitting a signal as a rectangular wave with a regular or
        varying "duty cycle"

    SBC
        Single Board Computer. An abbreviation typically applied to small
        computers like the Raspberry Pi which encapsulate the entire computer
        (including display controller, and all peripheral interfaces) on a
        single board. Typically only applies to machines that run "full"
        multi-tasking operating systems (like Linux), but *not* to
        micro-controllers like the Pico which only run a single task
        (Micropython, for instance).

    SD card
        `Secure Digital <https://en.wikipedia.org/wiki/SD_card>`_ cards are a
        common persistent storage media used in :term:`SBCs <SBC>` consisting
        of small, thumbnail sized cards with read/write capacities typically
        measured in tens of gigabytes.

    SSH
        The `secure shell <https://en.wikipedia.org/wiki/Secure_Shell>`_
        protocol used to remotely access machines typically running a
        `Unix-like <https://en.wikipedia.org/wiki/Unix-like>`_ :term:`OS`
