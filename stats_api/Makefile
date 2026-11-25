.PHONY: audit audit-fix check-dependencies-sync

check-dependencies-sync:
	python scripts/check_dependencies_sync.py

audit:
	python -m pip_audit -r requirements.txt
	python -m pip_audit .

audit-fix:
	python -m pip_audit -r requirements.txt --fix
	python -m pip_audit . --fix
