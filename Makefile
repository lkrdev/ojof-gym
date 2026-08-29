.PHONY: help eval eval-thelook eval-dry report report-offline lint lint-examples looker-validate looker-login clean

# Default Python interpreter
PYTHON ?= python3

help:
	@echo "OJOF-Gym Command Catalogue"
	@echo "=========================================================================="
	@echo "Benchmarking & Evaluations:"
	@echo "  make eval                  Run full multi-turn evaluation on all tasks"
	@echo "  make eval-thelook          Run multi-turn evaluation on task_thelook_ecommerce"
	@echo "  make eval-dry              Run benchmark in dry-run mode (no LLM tokens)"
	@echo ""
	@echo "Report & Verification Management:"
	@echo "  make report                Re-evaluate & rebuild reports from latest run"
	@echo "  make report-offline        Instantly regenerate report without re-querying Looker"
	@echo "  make report-run RUN=<dir>  Rebuild report for specific run export directory"
	@echo ""
	@echo "Linter & Looker Validation:"
	@echo "  make lint                  Run structural invariant linter on repository"
	@echo "  make lint-target DIR=<dir> Run structural invariant linter on target directory"
	@echo "  make looker-login          Authenticate and refresh Looker CLI session"
	@echo "=========================================================================="

eval:
	$(PYTHON) eval/run_benchmark.py --execute --model gemini-3.6-flash

eval-thelook:
	$(PYTHON) eval/run_benchmark.py --task task_thelook_ecommerce --execute --model gemini-3.6-flash

eval-dry:
	$(PYTHON) eval/run_benchmark.py --task task_thelook_ecommerce

report:
	$(PYTHON) eval/rebuild_report.py

report-offline:
	$(PYTHON) eval/rebuild_report.py --no-looker

report-run:
	$(PYTHON) eval/rebuild_report.py $(RUN)

lint:
	$(PYTHON) verifiers/ojof_linter.py .

lint-target:
	$(PYTHON) verifiers/ojof_linter.py $(DIR)

looker-login:
	~/.local/bin/with-looker looker-cli session login

clean:
	rm -rf /tmp/ojof_benchmark_*
