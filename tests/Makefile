.PHONY: audit audit-fix test test-unit test-integration

REPO_ROOT := $(abspath ..)

audit:
	python -m pip_audit -r requirements.txt

audit-fix:
	python -m pip_audit -r requirements.txt --fix

# `test` runs both packages; the other two run only the unit or only the integration tests.
# The integration tests start Postgres and Redis containers, so they need Docker.
test:
	cd "$(REPO_ROOT)" && python -m unittest discover -v -s tests -t .

test-unit:
	cd "$(REPO_ROOT)" && python -m unittest discover -v -s tests/unit -t .

test-integration:
	cd "$(REPO_ROOT)" && python -m unittest discover -v -s tests/integration -t .
