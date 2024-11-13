from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path
here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# Load requirements.txt
with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name='fandanGO-nmr-guf',
    version='0.1.0',
    description='nmr-guf plugin of the FandanGO application',
    long_description=long_description,
    author='CNB-CSIC, Carolina Simon, Irene Sanchez, Instruct-ERIC, Lui Holliday, Marcus Povey',
    author_email='carolina.simon@cnb.csic.es, isanchez@cnb.csic.es, lui.holliday@instruct-eric.org, marcus@instruct-eric.org',
    packages=find_packages(),
    install_requires=[requirements],
    entry_points={
        'fandango.plugin': 'fandanGO-nmr-guf = nmrguf'
    },
)
