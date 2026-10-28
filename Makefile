.PHONY: test validate-registry validate-cases

PYTHON ?= python3

test:
	$(PYTHON) -m unittest discover -s tests -v

validate-registry:
	$(PYTHON) -m deposium_bench validate-registry

validate-cases:
	$(PYTHON) -m deposium_bench validate-cases
