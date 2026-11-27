PYTHON_SERVICES := aggregator collector collector_metrics_agent firebase_housekeeping orchestrator ssid_geo_mapper stats stats_api tests util
GO_MODULES := cloudflare_limit_notifier collector_status_notifier db_backup firebase_limit_notifier home_server_limit_notifier util-go
# Go modules with tests behind the `integration` build tag. Their `test-integration` target runs all their tests.
# Keep in sync with the modules .github/workflows/go-tests.yml runs with -tags=integration.
GO_INTEGRATION_MODULES := collector_status_notifier db_backup firebase_limit_notifier util-go

AUDIT_TARGETS := $(addprefix audit-,$(PYTHON_SERVICES))
AUDIT_FIX_TARGETS := $(addprefix audit-fix-,$(PYTHON_SERVICES))
FMT_GO_TARGETS := $(addprefix fmt-go-,$(GO_MODULES))
LINT_GO_TARGETS := $(addprefix lint-go-,$(GO_MODULES))
TEST_GO_UNIT_TARGETS := $(addprefix test-go-unit-,$(GO_MODULES))
TEST_GO_INTEGRATION_TARGETS := $(addprefix test-go-integration-,$(GO_INTEGRATION_MODULES))

.PHONY: fmt fmt-python fmt-go fmt-react fmt-markdown $(FMT_GO_TARGETS)
.PHONY: lint lint-python lint-go lint-react lint-markdown lint-docker $(LINT_GO_TARGETS)
.PHONY: test test-python test-python-unit test-python-integration test-orchestrator
.PHONY: test-go test-go-unit test-go-integration $(TEST_GO_UNIT_TARGETS) $(TEST_GO_INTEGRATION_TARGETS)
.PHONY: audit-python audit-fix-python check-util-requirements-sync $(AUDIT_TARGETS) $(AUDIT_FIX_TARGETS)
.PHONY: scan-secrets

fmt: fmt-go fmt-react fmt-markdown fmt-python

fmt-python:
	python -m pre_commit run isort --all-files
	python -m pre_commit run black --all-files

fmt-go: $(FMT_GO_TARGETS)

$(FMT_GO_TARGETS): fmt-go-%:
	$(MAKE) -C $* fmt

fmt-react:
	$(MAKE) -C monitor_dashboard fmt

fmt-markdown:
	npm run fmt:markdown
	npm run lint:markdown:fix

lint: lint-go lint-react lint-python lint-markdown lint-docker

lint-python:
	python -m ruff check .

lint-go: $(LINT_GO_TARGETS)

$(LINT_GO_TARGETS): lint-go-%:
	$(MAKE) -C $* lint

lint-react:
	$(MAKE) -C monitor_dashboard lint

lint-docker:
	python -m pre_commit run hadolint --all-files

lint-markdown:
	npm run fmt:markdown:check
	npm run lint:markdown

# `test`, `test-python` and `test-go` run the same tests as CI, integration tests included, so they need Docker.
# The `-unit` targets skip the integration tests and need no Docker.
# The orchestrator tests are not part of `test`: they need Airflow installed (see orchestrator/Makefile).
test: test-python test-go

test-python:
	$(MAKE) -C tests test

test-python-unit:
	$(MAKE) -C tests test-unit

test-python-integration:
	$(MAKE) -C tests test-integration

test-orchestrator:
	$(MAKE) -C orchestrator test

# Runs the unit tests of every module first. Only when they all pass, the modules with integration tests run
# again with the `integration` tag, which runs their unit and integration tests together.
test-go:
	$(MAKE) test-go-unit
	$(MAKE) test-go-integration

# --keep-going runs the tests of every module, even after one of them fails.
test-go-unit:
	$(MAKE) --keep-going $(TEST_GO_UNIT_TARGETS)

test-go-integration:
	$(MAKE) --keep-going $(TEST_GO_INTEGRATION_TARGETS)

$(TEST_GO_UNIT_TARGETS): test-go-unit-%:
	$(MAKE) -C $* test

$(TEST_GO_INTEGRATION_TARGETS): test-go-integration-%:
	$(MAKE) -C $* test-integration

scan-secrets:
	python -m pre_commit run gitleaks --all-files

check-util-requirements-sync:
	python scripts/check_util_requirements_sync.py

audit-python:
	$(MAKE) --keep-going $(AUDIT_TARGETS)

audit-fix-python:
	$(MAKE) --keep-going $(AUDIT_FIX_TARGETS)

$(AUDIT_TARGETS): audit-%:
	$(MAKE) -C $* audit

$(AUDIT_FIX_TARGETS): audit-fix-%:
	$(MAKE) -C $* audit-fix
