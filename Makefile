PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
PYTEST ?= $(PYTHON) -m pytest
PYTHONPYCACHEPREFIX ?= __pycache__

.PHONY: syntax test smoke secret-scan check

syntax:
	PYTHONPYCACHEPREFIX=$(PYTHONPYCACHEPREFIX) $(PYTHON) -m compileall -q app agents orchestrator tests

test:
	$(PYTEST) tests/test_agent_inventory.py tests/test_auth_rbac.py tests/test_staff_audit.py tests/test_event_service.py tests/test_recommendation_service.py tests/test_financial_service.py -q

smoke:
	$(PYTEST) tests/test_process.py::test_auth_required tests/test_process.py::test_unsupported_file_type -q

secret-scan:
	! grep -R "firebase-adminsdk" -n . --exclude=Makefile --exclude=.gitignore --exclude-dir=.git --exclude-dir=.github --exclude-dir=.venv --exclude-dir=__pycache__
	! grep -R -E "BEGIN [A-Z ]*PRIVATE KEY" -n . --exclude=Makefile --exclude-dir=.git --exclude-dir=.github --exclude-dir=.venv --exclude-dir=__pycache__
	! grep -R "cdl-local-dev" -n frontend

check: syntax test smoke secret-scan
