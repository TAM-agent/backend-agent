# Deployment

Files and guides for deploying Intelligent Irrigation Agent to Google Cloud Run.

## 📁 Files

- **`Dockerfile`**: Docker container configuration
- **`cloudbuild.yaml`**: Google Cloud Build CI/CD pipeline
- **`Makefile`**: Automated deployment commands

## 🚀 Quick Deploy

### Option 1: Using Makefile (Recommended)

```bash
cd deployment
make deploy
```

### Option 2: Direct gcloud command

```bash
# From project root
gcloud run deploy intelligent-irrigation-agent \
  --source . \
  --region us-east1 \
  --project YOUR_PROJECT_ID \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --timeout 300
```

### Option 3: Cloud Build (CI/CD)

```bash
cd deployment
make cloud-build
```

## 📋 Makefile Commands

```bash
# See all available commands
cd deployment && make help

# Deployment
make deploy                 # Simple deploy
make deploy-with-secrets    # Deploy with Secret Manager secrets
make cloud-build           # Deploy via Cloud Build

# Local Docker
make build                 # Build image
make build-test           # Build and test locally

# Monitoring
make logs                  # View last 50 logs
make logs-tail            # Tail logs in real-time
make describe             # Service details
make url                  # Get service URL
make health              # Health check

# Information
make info                 # Deployment info
```

## 🔐 Secrets Management

If using Secret Manager for sensitive variables:

```bash
# Create secrets (first time only)
echo -n "your-api-key" | gcloud secrets create elevenlabs-api-key --data-file=-
echo -n "your-api-key" | gcloud secrets create usda-quickstats --data-file=-
echo -n "your-token" | gcloud secrets create telegram-bot-token --data-file=-

# Deploy with secrets
cd deployment && make deploy-with-secrets
```

## 🔍 Post-Deployment Verification

```bash
# 1. Get URL
cd deployment && make url

# 2. Health check
cd deployment && make health

# 3. View logs
cd deployment && make logs

# 4. Test endpoint
curl $(make url -s)/api/gardens/status
```

## 📊 File Structure

### Dockerfile

Builds Docker image with:
- Python 3.11 slim
- Project dependencies
- Non-root user for security
- Automatic health check

**Important**: Dockerfile is in `deployment/` but runs from project root to access all files.

### cloudbuild.yaml

CI/CD pipeline that:
1. Builds Docker image
2. Pushes to Google Container Registry
3. Deploys to Cloud Run automatically

### Makefile

Automated commands that:
- Read configuration from root `.env`
- Execute `gcloud` with correct parameters
- Handle errors and provide clear feedback

## ⚙️ Configuration

Environment variables are read from `.env` in project root:

```env
# Required
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-east1
GOOGLE_GENAI_USE_VERTEXAI=True
AI_MODEL=gemini-2.5-pro

# Optional (can be in Secret Manager)
USE_SIMULATION=true
USE_FIRESTORE=true
ELEVENLABS_API_KEY=...
USDA_QUICKSTATS_API_KEY=...
TELEGRAM_BOT_TOKEN=...
```

## 🐛 Troubleshooting

### Error: "Service account not found"
```bash
gcloud iam service-accounts create SERVICE_ACCOUNT_NAME \
  --display-name="Service Account Display Name"
```

### Error: "Permission denied"
```bash
# Grant necessary permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:SERVICE_ACCOUNT_NAME@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

### View detailed logs
```bash
cd deployment && make logs-tail
```

## 🔄 Rollback

If something goes wrong:

```bash
# List revisions
gcloud run revisions list \
  --service intelligent-irrigation-agent \
  --region us-east1

# Rollback to specific revision
gcloud run services update-traffic intelligent-irrigation-agent \
  --region us-east1 \
  --to-revisions REVISION_NAME=100
```

## 📚 Additional Documentation

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud Build Documentation](https://cloud.google.com/build/docs)
- [Main README](../README.md) - Complete project documentation

---

**Note**: Always run commands from the `deployment/` folder so relative paths work correctly.
