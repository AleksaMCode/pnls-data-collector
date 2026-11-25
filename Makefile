PYTHON_SERVICES := aggregator collector collector_metrics_agent firebase_housekeeping orchestrator ssid_geo_mapper stats stats_api tests util

AUDIT_TARGETS := $(addprefix audit-,$(PYTHON_SERVICES))
AUDIT_FIX_TARGETS := $(addprefix audit-fix-,$(PYTHON_SERVICES))

.PHONY: audit-python audit-fix-python check-util-requirements-sync $(AUDIT_TARGETS) $(AUDIT_FIX_TARGETS)

check-util-requirements-sync:
	python scripts/check_util_requirements_sync.py

audit-python: $(AUDIT_TARGETS)

audit-fix-python: $(AUDIT_FIX_TARGETS)

$(AUDIT_TARGETS): audit-%:
	$(MAKE) -C $* audit

$(AUDIT_FIX_TARGETS): audit-fix-%:
	$(MAKE) -C $* audit-fix
