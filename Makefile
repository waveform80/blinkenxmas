# vim: set noet sw=4 ts=4 fileencoding=utf-8:

# External utilities
PYTHON ?= python3
PIP ?= pip3
PYTEST ?= pytest
TWINE ?= twine
PYFLAGS ?=
DEST_DIR ?= /

# Find the location of GLib (only packaged for apt, not pip)
GLIB_APT:=$(wildcard /usr/lib/python3/dist-packages/gi)

# Calculate the base names of the distribution, the location of all source,
# documentation, packaging, icon, and executable script files
NAME:=$(shell $(PYTHON) $(PYFLAGS) setup.py --name)
WHEEL_NAME:=$(subst -,_,$(NAME))
VER:=$(shell $(PYTHON) $(PYFLAGS) setup.py --version)
PY_SOURCES:=$(shell \
	$(PYTHON) $(PYFLAGS) setup.py egg_info >/dev/null 2>&1 && \
	cat $(WHEEL_NAME).egg-info/SOURCES.txt | grep -v "\.egg-info"  | grep -v "\.mo$$")
DOC_SOURCES:=docs/conf.py \
	$(wildcard docs/*.png) \
	$(wildcard docs/*.svg) \
	$(wildcard docs/*.dot) \
	$(wildcard docs/*.mscgen) \
	$(wildcard docs/*.gpi) \
	$(wildcard docs/*.rst) \
	$(wildcard docs/*.pdf)
SUBDIRS:=

# Calculate the name of all outputs
DIST_WHEEL=dist/$(WHEEL_NAME)-$(VER)-py3-none-any.whl
DIST_TAR=dist/$(NAME)-$(VER).tar.gz
DIST_ZIP=dist/$(NAME)-$(VER).zip
MAN_PAGES=bxweb.1 bxcli.1 bxflash.1 blinkenxmas.conf.5


# Default target
all:
	@echo "make install - Install on local system"
	@echo "make develop - Install symlinks for development"
	@echo "make test - Run tests"
	@echo "make doc - Generate HTML and PDF documentation"
	@echo "make preview - Preview HTML documentation with local server"
	@echo "make source - Create source package"
	@echo "make wheel - Generate a PyPI wheel package"
	@echo "make zip - Generate a source zip package"
	@echo "make tar - Generate a source tar package"
	@echo "make dist - Generate all packages"
	@echo "make clean - Get rid of all generated files"
	@echo "make release - Create and tag a new release"
	@echo "make upload - Upload the new release to repositories"

install: $(SUBDIRS)
	$(PYTHON) $(PYFLAGS) setup.py install --root $(DEST_DIR)

doc: $(DOC_SOURCES)
	$(MAKE) -C docs clean
	$(MAKE) -C docs html
	$(MAKE) -C docs epub
	$(MAKE) -C docs latexpdf
	$(MAKE) $(MAN_PAGES)

preview:
	$(MAKE) -C docs preview

source: $(DIST_TAR) $(DIST_ZIP)

wheel: $(DIST_WHEEL)

zip: $(DIST_ZIP)

tar: $(DIST_TAR)

dist: $(DIST_WHEEL) $(DIST_TAR) $(DIST_ZIP)

develop:
	@# These have to be done separately to avoid a cockup...
	$(PIP) install -U setuptools
	$(PIP) install -U pip
	$(PIP) install -U twine
	$(PIP) install -U tox
	$(PIP) install -e .[doc,test]
ifeq ($(VIRTUAL_ENV),)
	@echo "Virtualenv not detected! You may need to link python3-gi manually"
else
ifeq ($(GLIB_APT),)
	@echo "WARNING: python3-gi not found. This is fine on non-Debian platforms"
else
	for lib in $(GLIB_APT); do ln -sf $$lib $(VIRTUAL_ENV)/lib/python*/site-packages/; done
endif
endif

test:
	$(PYTEST)

clean:
	rm -fr build/ dist/ man/ .pytest_cache/ .mypy_cache/ $(WHEEL_NAME).egg-info/ tags .coverage*
	for dir in docs $(SUBDIRS); do \
		$(MAKE) -C $$dir clean; \
	done
	find $(CURDIR) -name "*.pyc" -delete
	find $(CURDIR) -name "__pycache__" -delete

tags: $(PY_SOURCES)
	ctags -R --languages="Python" $(PY_SOURCES)

lint: $(PY_SOURCES)
	pylint $(WHEEL_NAME)

$(SUBDIRS):
	$(MAKE) -C $@

$(MAN_PAGES): $(DOC_SOURCES)
	$(MAKE) -C docs man
	mkdir -p man/
	cp build/man/*.[0-9] man/

$(DIST_TAR): $(PY_SOURCES) $(SUBDIRS)
	$(PYTHON) $(PYFLAGS) setup.py sdist --formats gztar

$(DIST_ZIP): $(PY_SOURCES) $(SUBDIRS)
	$(PYTHON) $(PYFLAGS) setup.py sdist --formats zip

$(DIST_WHEEL): $(PY_SOURCES) $(SUBDIRS)
	$(PYTHON) $(PYFLAGS) setup.py bdist_wheel

release:
	$(MAKE) clean
	test -z "$(shell git status --porcelain)"
	git tag -s release-$(VER) -m "Release $(VER)"
	git push origin release-$(VER)

upload: $(DIST_TAR) $(DIST_WHEEL)
	$(TWINE) check $(DIST_TAR) $(DIST_WHEEL)
	$(TWINE) upload $(DIST_TAR) $(DIST_WHEEL)

.PHONY: all install develop test doc source wheel zip tar dist clean tags release upload $(SUBDIRS)
