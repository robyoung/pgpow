# pgpow

[![PyPI](https://img.shields.io/pypi/v/pgpow.svg)](https://pypi.org/project/pgpow/)
[![Changelog](https://img.shields.io/github/v/release/robyoung/pgpow?include_prereleases&label=changelog)](https://github.com/robyoung/pgpow/releases)
[![Tests](https://github.com/robyoung/pgpow/actions/workflows/test.yml/badge.svg)](https://github.com/robyoung/pgpow/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/robyoung/pgpow/blob/master/LICENSE)

A command line toolkit for working with PostgreSQL.

## Installation

Install this tool using `pip`:
```bash
pip install pgpow
```
## Usage

For help, run:
```bash
pgpow --help
```
You can also use:
```bash
python -m pgpow --help
```
## Development

To contribute to this tool, first checkout the code. Then create a new virtual environment:
```bash
cd pgpow
python -m venv venv
source venv/bin/activate
```
Now install the dependencies and test dependencies:
```bash
pip install -e '.[test]'
```
To run the tests:
```bash
python -m pytest
```
