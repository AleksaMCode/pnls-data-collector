.PHONY: audit audit-fix test test-unit test-integration test-docker

# Keep in sync with the image in docker-compose.yml.
AIRFLOW_IMAGE := apache/airflow:3.4.0
REPO_ROOT := $(abspath ..)

audit:
	python -m pip_audit -r requirements.txt

audit-fix:
	python -m pip_audit -r requirements.txt --fix

# Runs the tests in the current Python environment, which needs Airflow installed (Linux or WSL only).
# `test` runs both packages; the other two run only the unit or only the integration tests.
test:
	cd $(REPO_ROOT) && python -m unittest discover -v -s orchestrator/tests -t .

test-unit:
	cd $(REPO_ROOT) && python -m unittest discover -v -s orchestrator/tests/unit -t .

test-integration:
	cd $(REPO_ROOT) && python -m unittest discover -v -s orchestrator/tests/integration -t .

# Runs the tests inside the same Airflow image that production uses. Needs only Docker.
test-docker:
	docker run --rm \
		-e PYTHONDONTWRITEBYTECODE=1 \
		-v "$(REPO_ROOT)":/repo:ro \
		-w /repo \
		--entrypoint python \
		$(AIRFLOW_IMAGE) -m unittest discover -v -s orchestrator/tests -t .
