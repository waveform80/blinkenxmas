#!/usr/bin/env python3
# vim: set fileencoding=utf-8:
#
# blinkenxmas: Making your Christmas tree vomit rainbows since 2023

import sys
import os
import configparser
from pathlib import Path
from datetime import datetime
from setuptools.config import read_configuration

on_rtd = os.environ.get('READTHEDOCS', '').lower() == 'true'
config = configparser.ConfigParser()
config.read([Path(__file__).parent / '..' / 'setup.cfg'])
info = config['metadata']

# -- Project information -----------------------------------------------------

project = info['name']
author = info['author']
now = datetime.now()
copyright = (
    f'2023-{now:%Y} {author}' if now.year > 2023 else f'2023 {author}')
release = info['version']
version = release

# -- General configuration ------------------------------------------------

needs_sphinx = '4.0'
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'sphinx.ext.imgmath',
]
if on_rtd:
    tags.add('rtd')

root_doc = 'index'
templates_path = ['_templates']
exclude_patterns = ['_build']
highlight_language = 'python3'
pygments_style = 'sphinx'

# -- Autodoc configuration ------------------------------------------------

autodoc_member_order = 'groupwise'
autodoc_default_options = {
    'members': True,
}
autodoc_mock_imports = []

# -- Intersphinx configuration --------------------------------------------

intersphinx_mapping = {
    'python': ('https://docs.python.org/3.10', None),
    'colorzero': ('https://colorzero.readthedocs.io/en/latest', None),
    'picamera': ('https://picamera.readthedocs.io/en/latest', None),
    'chameleon': ('https://chameleon.readthedocs.io/en/latest', None),
    'paho.mqtt': ('https://eclipse.dev/paho/files/paho.mqtt.python/html/', None),
}

# -- Options for HTML output ----------------------------------------------

html_theme = 'sphinx_rtd_theme'
html_title = f'{project} {version} Documentation'
html_static_path = ['_static']
manpages_url = 'https://manpages.ubuntu.com/manpages/jammy/en/man{section}/{page}.{section}.html'

# Hack to make wide tables work properly in RTD
# See https://github.com/snide/sphinx_rtd_theme/issues/117 for details
def setup(app):
    app.add_css_file('style_override.css')

# -- Options for LaTeX output ---------------------------------------------

latex_engine = 'xelatex'

latex_elements = {
    'papersize': 'a4paper',
    'pointsize': '10pt',
    'preamble': r'\def\thempfootnote{\arabic{mpfootnote}}', # workaround sphinx issue #2530
}

latex_documents = [
    (
        'index',            # source start file
        project + '.tex',   # target filename
        html_title,         # title
        author,             # author
        'manual',           # documentclass
        True,               # documents ref'd from toctree only
    ),
]

latex_show_pagerefs = True
latex_show_urls = 'footnote'

# -- Options for epub output ----------------------------------------------

epub_basename = project
epub_author = author
epub_identifier = f'https://{info["name"]}.readthedocs.io/'
epub_show_urls = 'no'

# -- Options for manual page output ---------------------------------------

man_pages = [
    ('bxweb', 'bxweb', 'bxweb -- The BlinkenXmas web server', [info['author']], 1),
    ('bxcli', 'bxcli', 'bxcli -- The BlinkenXmas command line client', [info['author']], 1),
    ('bxflash', 'bxflash', 'bxflash -- The BlinkenXmas Pico flashing tool', [info['author']], 1),
]

man_show_urls = True

# -- Options for linkcheck builder ----------------------------------------

linkcheck_retries = 3
linkcheck_workers = 20
linkcheck_anchors = True
