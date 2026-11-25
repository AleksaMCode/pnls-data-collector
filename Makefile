PYTHON_SERVICES := aggregator collector collector_metrics_agent firebase_housekeeping orchestrator ssid_geo_mapper stats stats_api tests util
GO_MODULES := cloudflare_limit_notifier collector_status_notifier db_backup firebase_limit_notifier home_server_limit_notifier util-go

AUDIT_TARGETS := $(addprefix audit-,$(PYTHON_SERVICES))
AUDIT_FIX_TARGETS := $(addprefix audit-fix-,$(PYTHON_SERVICES))
FMT_GO_TARGETS := $(addprefix fmt-go-,$(GO_MODULES))
LINT_GO_TARGETS := $(addprefix lint-go-,$(GO_MODULES))

.PHONY: fmt fmt-python fmt-go fmt-react fmt-markdown $(FMT_GO_TARGETS)
.PHONY: lint lint-python lint-go lint-react lint-markdown lint-docker $(LINT_GO_TARGETS)
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
