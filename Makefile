.PHONY: help install run single verify-sources stats test clean

PY ?= python3

help:
	@echo "make install         - install Python dependencies"
	@echo "make run             - LIVE run (real public sources); numbered PDF -> reports/ + ~/Downloads"
	@echo "make single          - rebuild the one-file program CTCannabisPoliticalCheck_app.py"
	@echo "make verify-sources  - print each source's recorded shape / verified_on"
	@echo "make stats           - row counts from the store"
	@echo "make test            - run the test suite (uses fixtures for engine validation only)"
	@echo "make clean           - remove out/ scratch outputs (KEEPS numbered reports/ + cache)"

install:
	$(PY) -m pip install -r requirements.txt

# Primary entry point: CTCannabisPoliticalCheck — LIVE ONLY. This is a journalistic
# investigative tool; it NEVER uses synthetic/demo data. Numbered non-overwriting PDF
# written to reports/ and copied to the top of ~/Downloads.
run:
	$(PY) CTCannabisPoliticalCheck.py

single:
	$(PY) build_single_file.py

verify-sources:
	$(PY) -m src.cli verify-sources

stats:
	$(PY) -m src.cli stats

test:
	$(PY) -m pytest -q

# NOTE: clean never touches reports/ (preserved, numbered) or data/cache/.
clean:
	rm -rf out/*.duckdb out/*.xlsx out/*.md out/*.csv out/*.png
