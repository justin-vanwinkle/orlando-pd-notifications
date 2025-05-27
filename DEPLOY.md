# Deployment Guide

This guide will help you deploy the Orlando PD Monitor to Azure Kubernetes Service (AKS) using GitHub Actions and GitHub Container Registry (GHCR).

## Prerequisites

- Azure subscription
- Azure CLI installed locally
- GitHub repository
- kubectl installed locally

## Step 1: Create Azure Resources

### 1.1 Create Resource Group
```bash
az group create --name orlando-pd-monitor-rg --location eastus
```

### 1.2 Create AKS Cluster
```bash
# Create AKS cluster
az aks create \
  --resource-group orlando-pd-monitor-rg \
  --name orlando-pd-monitor-aks \
  --node-count 1 \
  --node-vm-size Standard_B2s \
  --enable-managed-identity \
  --generate-ssh-keys
```

## Step 2: Get Azure Credentials

### 2.1 Create Service Principal for GitHub Actions
```bash
# Get subscription ID
SUBSCRIPTION_ID=$(az account show --query id --output tsv)

# Create service principal
az ad sp create-for-rbac \
  --name "orlando-pd-monitor-github" \
  --role contributor \
  --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/orlando-pd-monitor-rg \
  --json-auth

# This will output JSON that you'll use for AZURE_CREDENTIALS secret
```

## Step 3: Configure GitHub Secrets

In your GitHub repository, go to Settings → Secrets and variables → Actions, and create these secrets:

### Required Secrets:
- **`AZURE_CREDENTIALS`**: JSON output from service principal creation (step 2.1)
- **`RESEND_API_KEY`**: Your Resend API key (e.g., `re_YourApiKey123`)

**Note**: No container registry credentials needed! GitHub Container Registry (GHCR) automatically uses the `GITHUB_TOKEN` for authentication.

### Example AZURE_CREDENTIALS format:
```json
{
  "clientId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "clientSecret": "your-client-secret",
  "subscriptionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "tenantId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

## Step 4: Update GitHub Workflow

Edit `.github/workflows/deploy.yml` and replace these placeholders:

```yaml
env:
  CLUSTER_NAME: orlando-pd-monitor-aks
  CLUSTER_RESOURCE_GROUP: orlando-pd-monitor-rg
```

**Note**: No registry configuration needed! The workflow automatically uses `ghcr.io/${{ github.repository }}`.

## Step 5: Security Note

✅ **Secrets are handled securely!** 

The sensitive API key is stored in GitHub Secrets (not in your repository) and injected into Kubernetes at deployment time. Your public repository contains no sensitive information.

## Step 6: Deploy

### Option A: Deploy via GitHub Actions (Recommended)
1. Push your code to the `main` branch
2. GitHub Actions will automatically build and deploy

### Option B: Manual Deployment
```bash
# Get AKS credentials
az aks get-credentials --resource-group orlando-pd-monitor-rg --name orlando-pd-monitor-aks

# Build and push image to GHCR
docker build -t ghcr.io/your-username/police-notifications:latest .
echo $GITHUB_TOKEN | docker login ghcr.io -u your-username --password-stdin
docker push ghcr.io/your-username/police-notifications:latest

# Update deployment with your image
sed -i 's|<IMAGE_TAG>|ghcr.io/your-username/police-notifications:latest|g' k8s/deployment.yaml

# Deploy to Kubernetes
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/deployment.yaml

# Check deployment status
kubectl get pods -n orlando-pd-monitor
kubectl logs -f deployment/orlando-pd-monitor -n orlando-pd-monitor
```

## Step 7: Monitor and Troubleshoot

### Check deployment status:
```bash
kubectl get all -n orlando-pd-monitor
kubectl describe deployment orlando-pd-monitor -n orlando-pd-monitor
kubectl logs -f deployment/orlando-pd-monitor -n orlando-pd-monitor
```

### Scale the deployment:
```bash
kubectl scale deployment orlando-pd-monitor --replicas=2 -n orlando-pd-monitor
```

### Update configuration:
```bash
kubectl edit configmap orlando-pd-monitor-config -n orlando-pd-monitor
kubectl rollout restart deployment orlando-pd-monitor -n orlando-pd-monitor
```

## Cost Optimization

The deployment uses minimal resources:
- **AKS**: 1 x Standard_B2s node (~$60/month)
- **GHCR**: Free for public repositories, $0.50/GB for private
- **Application**: 64Mi memory, 50m CPU

For production, consider:
- Using Azure Container Instances (ACI) for lower cost (~$10/month)
- Implementing horizontal pod autoscaling
- Setting up monitoring with Azure Monitor

## Security Notes

- Store sensitive configuration in Kubernetes Secrets
- Use Azure Key Vault for production secrets
- Enable network policies in AKS for enhanced security
- Regularly update container images for security patches 