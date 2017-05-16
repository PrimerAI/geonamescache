.PHONY: clean docs

help:
	@echo "clean - remove all build, test, coverage and Python artifacts"
	@echo "clean-build - remove build artifacts"
	@echo "clean-pyc - remove Python file artifacts"
	@echo "clean-test - remove test and coverage artifacts"
	@echo "dl_all - download geonames data"
	@echo "dist - package"
	@echo "docs - generate Sphinx HTML documentation, including API docs"
	@echo "docs-release - generate and upload docs to PyPI"
	@echo "test - run tests quickly with the default Python"
	@echo "test-all - run tests on every Python version with tox"
	@echo "release - package and upload a release"

dl_cities:
	curl -o data/cities5000.zip http://download.geonames.org/export/dump/cities5000.zip
	unzip data/cities5000.zip -d data

dl_countries:
	curl -o data/countryInfo.txt http://download.geonames.org/export/dump/countryInfo.txt

dl_admin_1s:
	curl -o data/admin1Codes.txt http://download.geonames.org/export/dump/admin1CodesASCII.txt

dl_admin_2s:
	curl -o data/admin2Codes.txt http://download.geonames.org/export/dump/admin2Codes.txt

dl_all:
	make dl_cities
	make dl_countries
	make dl_admin_1s
	make dl_admin_2s

clean: clean-build clean-pyc clean-test

clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean-test:
	rm -fr .tox/
	rm -f .coverage
	rm -fr htmlcov/

dist: clean
	python setup.py sdist
	python setup.py bdist_wheel

docs:
	rm -f docs/geonamescache.rst
	rm -f docs/modules.rst
	sphinx-apidoc -o docs/ geonamescache
	$(MAKE) -C docs clean
	$(MAKE) -C docs html
	firefox docs/_build/html/index.html

docs-release: docs
	python setup.py upload_docs

install: clean
	pip install -r dev_requirements.txt --use-mirrors
	python setup.py install

release: clean
	python setup.py sdist upload
	python setup.py bdist_wheel upload

test:
	python setup.py test

test-all:
	tox
