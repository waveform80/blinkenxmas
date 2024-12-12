===================
I've got the Power!
===================

The power supply requires some consideration. Neopixels typically have a
maximum output power of 0.24W per LED (at 5V). All told I've got 150 LEDs, so
that's a total potential output of 150 × 0.24W = 36W, plus whatever's required
for the Pico but frankly that'll be so minimal by comparison it's not worth
worrying about.

At 5V that's 36W ÷ 5V = 7.2A which is *way* beyond the maximum output of the
typical micro-USB power supply used with Picos; these often top out at 1A or
2A.

We need something quite a bit bigger, and preferably with a decent amount of
overhead [#overhead]_. I'll be using an `5V 100W supply`_ which gives me 64W of
head-room, but I'd guesstimate that anything 50W+ should be sufficient.

.. image:: images/psu.*
    :align: center
    :alt: The power supply used in the tutorial. A large metal cuboid with
          several screw terminals at the rear (for mains input and 5V outputs)
          all surrounded by perforated aluminium for passive air cooling

.. warning::

    Please note that most of these supplies do not come with mains cables. This
    is why I included "being comfortable with wiring mains cables to a power
    supply" in the skills list at the top. You will need to be confident that
    you know which leads are live, neutral, and ground, when wiring this thing
    up.


The Heat Is On
==============

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
stick all this in a non-flammable box!

.. _5V 100W supply: https://www.amazon.co.uk/Baiyouli-Universal-Regulated-Switching-10W-300W/dp/B07D6R2ZBK

----

.. [#overhead] It's rarely a good idea to run power supplies near their limits.
   Even if they do manage it, you'll often experience voltage drops which can
   lead to brown-outs or crashes on your micro-controller. Such issues are
   notoriously hard to debug, so give yourself some reasonable overhead on the
   power supply.
