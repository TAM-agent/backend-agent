# Makefile for Deployment
# Run from deployment/ folder
# All commands execute in project root context

# Get project root directory
PROJECT_ROOT := ..

# Project configuration (read from root .env)
PROJECT_ID := $(shell cd $(PROJECT_ROOT) && grep GOOGLE_CLOUD_PROJECT .env 2>/dev/null | cut -d '=' -f2 | tr -d '"' || echo "")
SERVICE_NAME := intelligent-irrigation-agent
REGION := us-east1

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

.PHONY: help
help: ## Show this help message
	@echo "$(GREEN)Intelligent Irrigation Agent - Deployment Commands$(NC)"
	@echo ""
	@echo "$(YELLOW)Run from deployment/ folder$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)Examples:$(NC)"
	@echo "  cd deployment && make deploy"
	@echo "  cd deployment && make logs"

# ============================================================================
# DOCKER BUILD
# ============================================================================

.PHONY: build
build: ## Build Docker image locally
	@echo "$(GREEN)Building Docker image...$(NC)"
	cd $(PROJECT_ROOT) && docker build -f deployment/Dockerfile -t $(SERVICE_NAME):latest .

.PHONY: build-test
build-test: build ## Build and test Docker image locally
	@echo "$(GREEN)Testing Docker image...$(NC)"
	docker run --rm -p 8080:8080 -e PORT=8080 $(SERVICE_NAME):latest

# ============================================================================
# CLOUD RUN DEPLOYMENT
# ============================================================================

.PHONY: deploy
deploy: ## Deploy to Google Cloud Run
	@echo "$(GREEN)Deploying to Cloud Run...$(NC)"
	@if [ -z "$(PROJECT_ID)" ]; then \
		echo "$(RED)ERROR: GOOGLE_CLOUD_PROJECT not set in ../.env$(NC)"; \
		exit 1; \
	fi
	cd $(PROJECT_ROOT) && gcloud run deploy $(SERVICE_NAME) \
		--source . \
		--region $(REGION) \
		--project $(PROJECT_ID) \
		--allow-unauthenticated \
		--memory 512Mi \
		--cpu 1 \
		--timeout 300 \
		--max-instances=10 \
		--min-instances=0

.PHONY: deploy-with-secrets
deploy-with-secrets: ## Deploy with secrets from Secret Manager
	@echo "$(GREEN)Deploying with secrets...$(NC)"
	@if [ -z "$(PROJECT_ID)" ]; then \
		echo "$(RED)ERROR: GOOGLE_CLOUD_PROJECT not set in ../.env$(NC)"; \
		exit 1; \
	fi
	cd $(PROJECT_ROOT) && gcloud run deploy $(SERVICE_NAME) \
		--source . \
		--region $(REGION) \
		--project $(PROJECT_ID) \
		--allow-unauthenticated \
		--memory 512Mi \
		--cpu 1 \
		--timeout 300 \
		--set-env-vars GOOGLE_CLOUD_PROJECT=$(PROJECT_ID) \
		--set-env-vars GOOGLE_CLOUD_LOCATION=$(REGION) \
		--set-env-vars GOOGLE_GENAI_USE_VERTEXAI=true \
		--set-env-vars AI_MODEL=gemini-2.5-pro \
		--set-env-vars USE_SIMULATION=true \
		--set-env-vars USE_FIRESTORE=true \
		--set-secrets ELEVENLABS_API_KEY=elevenlabs-api-key:latest \
		--set-secrets USDA_QUICKSTATS_API_KEY=usda-quickstats:latest \
		--set-secrets TELEGRAM_BOT_TOKEN=telegram-bot-token:latest

.PHONY: cloud-build
cloud-build: ## Deploy using Cloud Build (CI/CD)
	@echo "$(GREEN)Deploying via Cloud Build...$(NC)"
	@if [ -z "$(PROJECT_ID)" ]; then \
		echo "$(RED)ERROR: GOOGLE_CLOUD_PROJECT not set in ../.env$(NC)"; \
		exit 1; \
	fi
	cd $(PROJECT_ROOT) && gcloud builds submit \
		--config=deployment/cloudbuild.yaml \
		--project=$(PROJECT_ID)

# ============================================================================
# MONITORING AND LOGS
# ============================================================================

.PHONY: logs
logs: ## View deployment logs (last 50 lines)
	@echo "$(GREEN)Fetching logs...$(NC)"
	gcloud run services logs read $(SERVICE_NAME) \
		--region $(REGION) \
		--project $(PROJECT_ID) \
		--limit 50

.PHONY: logs-tail
logs-tail: ## Tail deployment logs in real-time
	@echo "$(GREEN)Tailing logs (Ctrl+C to stop)...$(NC)"
	gcloud run services logs tail $(SERVICE_NAME) \
		--region $(REGION) \
		--project $(PROJECT_ID)

.PHONY: describe
describe: ## Show service details
	@echo "$(GREEN)Service details:$(NC)"
	gcloud run services describe $(SERVICE_NAME) \
		--region $(REGION) \
		--project $(PROJECT_ID)

.PHONY: url
url: ## Get service URL
	@gcloud run services describe $(SERVICE_NAME) \
		--region $(REGION) \
		--project $(PROJECT_ID) \
		--format='value(status.url)'

.PHONY: health
health: ## Check service health
	@echo "$(GREEN)Checking health...$(NC)"
	@SERVICE_URL=$$(gcloud run services describe $(SERVICE_NAME) \
		--region $(REGION) \
		--project $(PROJECT_ID) \
		--format='value(status.url)'); \
	curl -s $$SERVICE_URL/health | jq .

# ============================================================================
# UTILITIES
# ============================================================================

.PHONY: info
info: ## Show deployment info
	@echo "$(GREEN)Deployment Information:$(NC)"
	@echo "  Project ID: $(PROJECT_ID)"
	@echo "  Service: $(SERVICE_NAME)"
	@echo "  Region: $(REGION)"
	@echo ""
	@echo "$(YELLOW)Service URL:$(NC)"
	@$(MAKE) -s url
