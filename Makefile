# Books Scraper Makefile

.PHONY: venv install test run clean lint format

venv:
	python -m venv .venv

install: venv
	./.venv/bin/pip install -r requirements.txt

test: install
	./.venv/bin/pytest tests/ -v --timeout=10

run: install
	./.venv/bin/python scraper.py

lint: install
	./.venv/bin/pip install ruff
	./.venv/bin/ruff check scraper.py tests/

format: install
	./.venv/bin/pip install ruff
	./.venv/bin/ruff format scraper.py tests/

clean:
	rm -rf .venv/ __pycache__/ .pytest_cache/
	find . -name "*.pyc" -delete
