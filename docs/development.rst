===========
Development
===========

.. currentmodule:: blinkenxmas

The main GitHub repository for the project can be found at:

    https://github.com/waveform80/blinkenxmas


.. _dev_install:

Development installation
========================

If you wish to develop blinkenxmas, obtain the source by cloning the GitHub
repository and then use the "develop" target of the Makefile which will install
the package as a link to the cloned repository allowing in-place development.
The following example demonstrates this method within a virtual Python
environment:

.. code-block:: console

    $ sudo apt install build-essential git virtualenvwrapper

After installing ``virtualenvwrapper`` you'll need to restart your shell before
commands like :command:`mkvirtualenv` will operate correctly. Once you've
restarted your shell, continue:

.. code-block:: console

    $ cd
    $ mkvirtualenv -p /usr/bin/python3 blinkenxmas
    $ workon blinkenxmas
    (blinkenxmas) $ git clone https://github.com/waveform80/blinkenxmas.git
    (blinkenxmas) $ cd blinkenxmas
    (blinkenxmas) $ make develop

To pull the latest changes from git into your clone and update your
installation:

.. code-block:: console

    $ workon blinkenxmas
    (blinkenxmas) $ cd ~/blinkenxmas
    (blinkenxmas) $ git pull
    (blinkenxmas) $ make develop

To remove your installation, destroy the sandbox and the clone:

.. code-block:: console

    (blinkenxmas) $ deactivate
    $ rmvirtualenv blinkenxmas
    $ rm -rf ~/blinkenxmas


Building the docs
=================

If you wish to build the docs, you'll need a few more dependencies. Inkscape
is used for conversion of SVGs to other formats, Graphviz is used for rendering
certain charts, and TeX Live is required for building PDF output. The following
command should install all required dependencies:

.. code-block:: console

    $ sudo apt install texlive-latex-recommended texlive-latex-extra \
        texlive-fonts-recommended texlive-xetex graphviz inkscape \
        python3-sphinx python3-sphinx-rtd-theme latexmk xindy

Once these are installed, you can use the "doc" target to build the
documentation in all supported formats (HTML, ePub, and PDF):

.. code-block:: console

    $ workon blinkenxmas
    (blinkenxmas) $ cd ~/blinkenxmas
    (blinkenxmas) $ make doc

However, the easiest way to develop the documentation is with the "preview"
target which will build the HTML version of the docs, and start a web-server to
preview the output. The web-server will then watch for source changes (in both
the documentation source, and the application's source) and rebuild the HTML
automatically as required:

.. code-block:: console

    $ workon blinkenxmas
    (blinkenxmas) $ cd ~/blinkenxmas
    (blinkenxmas) $ make preview

The HTML output is written to :file:`build/html` while the PDF output
goes to :file:`build/latex`.
