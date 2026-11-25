.PHONY: audit audit-fix test test-unit test-integration test-docker

# Keep in sync with the image in docker-compose.yml.
AIRFLOW_IMAGE := apache/airflow:3.4.0
REPO_ROOT := $(abspath ..)

DOCKER_PYTHON := docker run --rm \
	-e PYTHONDONTWRITEBYTECODE=1 \
	-v "$(REPO_ROOT)":/repo:ro \
	-w /repo \
	--entrypoint python \
	$(AIRFLOW_IMAGE)

audit:
	python -m pip_audit -r requirements.txt

audit-fix:
	python -m pip_audit -r requirements.txt --fix

# Runs the tests in the current Python environment, which needs Airflow installed (Linux or WSL only).
# `test` runs the unit and integration packages in separate processes, as CI does. In one process,
# the integration tests would create the metadata database and hide unit tests that need it by mistake.
test: test-unit test-integration

test-unit:
	cd $(REPO_ROOT) && python -m unittest discover -v -s orchestrator/tests/unit -t .

test-integration:
	cd $(REPO_ROOT) && python -m unittest discover -v -s orchestrator/tests/integration -t .

# Runs the tests inside the same Airflow image that production uses. Needs only Docker.
test-docker:
	$(DOCKER_PYTHON) -m unittest discover -v -s orchestrator/tests/unit -t .
	$(DOCKER_PYTHON) -m unittest discover -v -s orchestrator/tests/integration -t .
