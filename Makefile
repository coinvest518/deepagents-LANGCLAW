PACKAGE_DIRS := $(sort $(patsubst %/,%,$(dir $(wildcard libs/*/Makefile libs/partners/*/Makefile))))

# Map package dirs to their required Python version
# acp requires 3.14, everything else uses 3.12
python_version = $(if $(filter libs/acp,$1),3.14,3.12)

.PHONY: help lock lock-check lint format dev dev-backend dev-dashboard

.DEFAULT_GOAL := help

# Windows: .venv/Scripts/python — Unix: override with `make dev PYTHON=.venv/bin/python`
PYTHON ?= .venv/Scripts/python

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

lock: ## Update all lockfiles
	@set -e; \
	for dir in $(PACKAGE_DIRS); do \
		echo "🔒 Locking $$dir"; \
		uv lock --directory $$dir --python $(call python_version,$$dir); \
	done
	@echo "✅ All lockfiles updated!"

lock-check: ## Check all lockfiles are up-to-date
	@set -e; \
	for dir in $(PACKAGE_DIRS); do \
		echo "🔍 Checking $$dir"; \
		uv lock --check --directory $$dir --python $(call python_version,$$dir); \
	done
	@echo "✅ All lockfiles are up-to-date!"

lint: ## Lint all packages
	@set -e; \
	for dir in $(PACKAGE_DIRS); do \
		echo "🔍 Linting $$dir"; \
		$(MAKE) -C $$dir lint; \
	done
	@echo "✅ All packages linted!"

format: ## Format all packages
	@set -e; \
	for dir in $(PACKAGE_DIRS); do \
		echo "🎨 Formatting $$dir"; \
		$(MAKE) -C $$dir format; \
	done
	@echo "✅ All packages formatted!"

dev: ## Start backend (:10000) and dashboard (:3001) in parallel
	@echo "Starting backend + dashboard. Ctrl-C to stop both."
	@$(MAKE) -j2 dev-backend dev-dashboard

dev-backend: ## Run the local dashboard server (full agent on :10000)
	$(PYTHON) scripts/local_dashboard_server.py

dev-dashboard: ## Run the Next.js dashboard on :3001
	cd dashboard && npm run dev
