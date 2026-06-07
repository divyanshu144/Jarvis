.PHONY: check test fmt lint run

check: fmt lint test

test:
	python3 -m pytest -v

fmt:
	python3 -m compileall jarvis tests jarvis.py setup_google.py

lint:
	python3 -m py_compile jarvis.py jarvis/core/*.py jarvis/tools/*.py tests/test_routing.py

run:
	python3 jarvis.py
