PYTHON_SERVICES := aggregator collector collector_metrics_agent firebase_housekeeping orchestrator ssid_geo_mapper stats stats_api tests util
GO_MODULES := cloudflare_limit_notifier collector_status_notifier db_backup firebase_limit_notifier home_server_limit_notifier util-go

AUDIT_TARGETS := $(addprefix audit-,$(PYTHON_SERVICES))
AUDIT_FIX_TARGETS := $(addprefix audit-fix-,$(PYTHON_SERVICES))
FMT_GO_TARGETS := $(addprefix fmt-go-,$(GO_MODULES))

.PHONY: fmt fmt-python fmt-go fmt-react $(FMT_GO_TARGETS)
.PHONY: audit-python audit-fix-python check-util-requirements-sync $(AUDIT_TARGETS) $(AUDIT_FIX_TARGETS)

fmt: fmt-go fmt-react fmt-python

fmt-python:
	pre-commit run --all-files

fmt-go: $(FMT_GO_TARGETS)

$(FMT_GO_TARGETS): fmt-go-%:
	$(MAKE) -C $* fmt

fmt-react:
	$(MAKE) -C monitor_dashboard fmt

check-util-requirements-sync:
	python scripts/check_util_requirements_sync.py

audit-python: $(AUDIT_TARGETS)

audit-fix-python: $(AUDIT_FIX_TARGETS)

$(AUDIT_TARGETS): audit-%:
	$(MAKE) -C $* audit

$(AUDIT_FIX_TARGETS): audit-fix-%:
	$(MAKE) -C $* audit-fix
