.PHONY: help install run run-live verify-sources stats test clean

PY ?= python3

help:
	@echo "make install         - install Python dependencies"
	@echo "make run             - LIVE run (data.ct.gov); numbered PDF -> reports/ + ~/Downloads"
	@echo "make run-offline     - offline demo run (bundled fixtures, zero live requests)"
	@echo "make verify-sources  - print each source's recorded shape / verified_on"
	@echo "make stats           - row counts from the store"
	@echo "make test            - run the test suite"
	@echo "make clean           - remove out/ scratch outputs (KEEPS numbered reports/ + cache)"

install:
	$(PY) -m pip install -r requirements.txt

# Primary entry point: CTCannabisPoliticalCheck — LIVE run, numbered non-overwriting
# PDF written to reports/ and copied to the top of ~/Downloads.
run:
	$(PY) CTCannabisPoliticalCheck.py

run-offline:
	$(PY) CTCannabisPoliticalCheck.py --offline

verify-sources:
	$(PY) -m src.cli verify-sources

stats:
	$(PY) -m src.cli stats

test:
	$(PY) -m pytest -q

# NOTE: clean never touches reports/ (preserved, numbered) or data/cache/.
clean:
	rm -rf out/*.duckdb out/*.xlsx out/*.md out/*.csv out/*.png
