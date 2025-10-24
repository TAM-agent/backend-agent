# Makefile for Intelligent Irrigation Agent
# Provides convenient commands for development, testing, and deployment

# Python executable
PYTHON := python
PIP := pip

# Project configuration
PROJECT_ID := $(shell grep GOOGLE_CLOUD_PROJECT .env 2>/dev/null | cut -d '=' -f2 | tr -d '"' || echo "")
SERVICE_NAME := intelligent-irrigation-agent
REGION := us-east1

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

.PHONY: help
help: ## Show this help message
	@echo "$(GREEN)Intelligent Irrigation Agent - Development Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'

# ============================================================================
# SETUP AND INSTALLATION
# ============================================================================

.PHONY: install
install: ## Install production dependencies
	@echo "$(GREEN)Installing production dependencies...$(NC)"
	$(PIP) install -r requirements.txt

.PHONY: install-dev
install-dev: ## Install all dependencies (including dev tools)
	@echo "$(GREEN)Installing all dependencies...$(NC)"
	$(PIP) install -r requirements.txt

.PHONY: setup-env
setup-env: ## Create .env file from template
	@if [ ! -f .env ]; then \
		echo "$(GREEN)Creating .env file from template...$(NC)"; \
		cp .env-template .env; \
		echo "$(YELLOW)Please edit .env file with your configuration$(NC)"; \
	else \
		echo "$(YELLOW).env file already exists$(NC)"; \
	fi

.PHONY: setup
setup: setup-env install-dev ## Complete development setup
	@echo "$(GREEN)Development environment setup complete!$(NC)"
	@echo "$(YELLOW)Next steps:$(NC)"
	@echo "  1. Edit .env file with your API keys and configuration"
	@echo "  2. Run 'make test' to verify installation"
	@echo "  3. Run 'make run' to start the agent locally"

# ============================================================================
# DEVELOPMENT
# ============================================================================

.PHONY: run
run: ## Run the agent locally
	@echo "$(GREEN)Starting intelligent irrigation agent...$(NC)"
	$(PYTHON) -m irrigation_agent.agent

.PHONY: playground
playground: ## Start local development playground
	@echo "$(GREEN)Starting development playground...$(NC)"
	$(PYTHON) -m irrigation_agent.playground

.PHONY: test
test: ## Run tests
	@echo "$(GREEN)Running tests...$(NC)"
	pytest tests/ -v

.PHONY: test-tools
test-tools: ## Test individual tools
	@echo "$(GREEN)Testing tools...$(NC)"
	$(PYTHON) -c "from irrigation_agent.tools import *; import json; print(json.dumps(get_system_status(), indent=2))"

.PHONY: lint
lint: ## Run linting checks
	@echo "$(GREEN)Running linting checks...$(NC)"
	@echo "$(YELLOW)Note: Install ruff for linting: pip install ruff$(NC)"
	-ruff check irrigation_agent/

.PHONY: format
format: ## Format code
	@echo "$(GREEN)Formatting code...$(NC)"
	@echo "$(YELLOW)Note: Install ruff for formatting: pip install ruff$(NC)"
	-ruff format irrigation_agent/

# ============================================================================
# GOOGLE CLOUD DEPLOYMENT
# ============================================================================

.PHONY: setup-gcp
setup-gcp: ## Setup Google Cloud project
	@echo "$(GREEN)Setting up Google Cloud project...$(NC)"
	@if [ -z "$(PROJECT_ID)" ]; then \
		echo "$(RED)ERROR: GOOGLE_CLOUD_PROJECT not set in .env$(NC)"; \
		exit 1; \
	fi
	gcloud config set project $(PROJECT_ID)
	gcloud services enable aiplatform.googleapis.com
	gcloud services enable run.googleapis.com
	@echo "$(GREEN)Google Cloud project setup complete$(NC)"

.PHONY: deploy
deploy: ## Deploy to Google Cloud Run (no authentication required)
	@echo "$(GREEN)Deploying to Cloud Run...$(NC)"
	@if [ -z "$(PROJECT_ID)" ]; then \
		echo "$(RED)ERROR: GOOGLE_CLOUD_PROJECT not set in .env$(NC)"; \
		exit 1; \
	fi
	gcloud run deploy $(SERVICE_NAME) \
		--source . \
		--region $(REGION) \
		--project $(PROJECT_ID) \
		--allow-unauthenticated \
		--memory 512Mi \
		--cpu 1 \
		--timeout 300

.PHONY: deploy-auth
deploy-auth: ## Deploy to Cloud Run (authentication required)
	@echo "$(GREEN)Deploying to Cloud Run with authentication...$(NC)"
	@if [ -z "$(PROJECT_ID)" ]; then \
		echo "$(RED)ERROR: GOOGLE_CLOUD_PROJECT not set in .env$(NC)"; \
		exit 1; \
	fi
	gcloud run deploy $(SERVICE_NAME) \
		--source . \
		--region $(REGION) \
		--project $(PROJECT_ID) \
		--no-allow-unauthenticated \
		--memory 512Mi \
		--cpu 1 \
		--timeout 300

.PHONY: logs
logs: ## View deployment logs
	@echo "$(GREEN)Fetching logs...$(NC)"
	gcloud run services logs read $(SERVICE_NAME) \
		--region $(REGION) \
		--project $(PROJECT_ID) \
		--limit 50

.PHONY: status
status: ## Check deployment status
	@echo "$(GREEN)Checking deployment status...$(NC)"
	gcloud run services describe $(SERVICE_NAME) \
		--region $(REGION) \
		--project $(PROJECT_ID)

# ============================================================================
# MONITORING AND OPERATIONS
# ============================================================================

.PHONY: monitor
monitor: ## Monitor system status
	@echo "$(GREEN)Monitoring irrigation system...$(NC)"
	$(PYTHON) -c "from irrigation_agent.tools import get_system_status; import json; status=get_system_status(); print(json.dumps(status, indent=2)); print(f\"\\nOverall Health: {status['overall_health'].upper()}\")"

.PHONY: check-sensors
check-sensors: ## Check all sensor readings
	@echo "$(GREEN)Checking sensor readings...$(NC)"
	$(PYTHON) -c "from irrigation_agent.tools import check_soil_moisture, check_water_tank_level; import json; plants=['tomato','basil','lettuce','pepper']; [print(f\"{p}: {check_soil_moisture(p)['moisture_level']}%\") for p in plants]; tank=check_water_tank_level(); print(f\"Tank: {tank['level_percentage']}%\")"

.PHONY: check-weather
check-weather: ## Check weather forecast
	@echo "$(GREEN)Checking weather forecast...$(NC)"
	$(PYTHON) -c "from irrigation_agent.tools import get_weather_forecast; import json; forecast=get_weather_forecast(); print(json.dumps(forecast, indent=2))"

# ============================================================================
# CLEANUP
# ============================================================================

.PHONY: clean
clean: ## Clean up temporary files
	@echo "$(GREEN)Cleaning up...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)Cleanup complete$(NC)"

.PHONY: undeploy
undeploy: ## Delete Cloud Run deployment
	@echo "$(YELLOW)Deleting Cloud Run service...$(NC)"
	gcloud run services delete $(SERVICE_NAME) \
		--region $(REGION) \
		--project $(PROJECT_ID) \
		--quiet

# ============================================================================
# UTILITIES
# ============================================================================

.PHONY: version
version: ## Show version information
	@echo "$(GREEN)Intelligent Irrigation Agent$(NC)"
	@echo "Version: 0.1.0"
	@echo "Python: $(shell $(PYTHON) --version)"
	@echo "Project ID: $(PROJECT_ID)"

.PHONY: env-check
env-check: ## Validate environment configuration
	@echo "$(GREEN)Checking environment configuration...$(NC)"
	@$(PYTHON) -c "from irrigation_agent.config import config, iot_config, weather_config; \
		print(f'Worker Model: {config.worker_model}'); \
		print(f'Critic Model: {config.critic_model}'); \
		print(f'Raspberry Pi: {iot_config.raspberry_pi_ip}:{iot_config.backend_port}'); \
		print(f'Weather API: {\"Configured\" if weather_config.openweather_api_key else \"NOT CONFIGURED\"}'); \
		print(f'Polling Interval: {config.sensor_polling_interval}s')"

# ============================================================================
# COMPLETE WORKFLOWS
# ============================================================================

.PHONY: full-deploy
full-deploy: setup-gcp deploy ## Complete deployment workflow
	@echo "$(GREEN)Full deployment complete!$(NC)"
	@echo "Run '$(YELLOW)make logs$(NC)' to view deployment logs"
	@echo "Run '$(YELLOW)make status$(NC)' to check service status"

.PHONY: dev-cycle
dev-cycle: clean install-dev test ## Complete development cycle
	@echo "$(GREEN)Development cycle complete!$(NC)"
