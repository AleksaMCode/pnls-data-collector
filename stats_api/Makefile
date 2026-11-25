.PHONY: audit audit-fix check-dependencies-sync sync-pyproject-dependencies

check-dependencies-sync:
	python scripts/check_dependencies_sync.py

sync-pyproject-dependencies:
	python scripts/sync_pyproject_dependencies.py

audit:
	python -m pip_audit -r requirements.txt
	python -m pip_audit .

audit-fix:
	-python -m pip_audit -r requirements.txt --fix
	python scripts/sync_pyproject_dependencies.py
	python scripts/check_dependencies_sync.py
	python -m pip_audit -r requirements.txt
