#!/usr/bin/env bash
# =========================================================================
# provision.sh  —  Initialize and provision Azure Container Apps resources
# =========================================================================

set -euo pipefail

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*"; }

# Resolve directory of this script to run context-independent
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check Azure CLI
if ! command -v az &>/dev/null; then
  error "Azure CLI ('az') is not installed. Please install it first: https://docs.microsoft.com/cli/azure/install-azure-cli"
  exit 1
fi

# Ensure user is logged in
info "Checking Azure login status..."
if ! az account show &>/dev/null; then
  warn "Not logged into Azure. Initiating login flow..."
  az login
fi

# Ensure required resource providers are registered
info "Ensuring required Azure Resource Providers (Microsoft.App, Microsoft.ContainerRegistry, Microsoft.OperationalInsights) are registered..."
az provider register --namespace Microsoft.App --wait
az provider register --namespace Microsoft.ContainerRegistry --wait
az provider register --namespace Microsoft.OperationalInsights --wait

# Configuration Defaults
RESOURCE_GROUP="cinemagic-rg"
LOCATION="eastus"
APP_NAME="cinemagic-app"

read -p "Enter Azure Resource Group Name [$RESOURCE_GROUP]: " input_rg
RESOURCE_GROUP=${input_rg:-$RESOURCE_GROUP}

read -p "Enter Azure Location (Region) [$LOCATION]: " input_loc
LOCATION=${input_loc:-$LOCATION}

info "Creating Resource Group '$RESOURCE_GROUP' in region '$LOCATION'..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output table

# Read variables from .env to auto-configure secrets
get_env_val() {
  local key=$1
  if [[ -f "../.env" ]]; then
    grep "^${key}[[:space:]]*=" ../.env | tail -n 1 | cut -d'=' -f2- | tr -d '"'\''\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' || echo ""
  elif [[ -f ".env" ]]; then
    grep "^${key}[[:space:]]*=" .env | tail -n 1 | cut -d'=' -f2- | tr -d '"'\''\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' || echo ""
  else
    echo ""
  fi
}

info "Reading database and API credentials from local .env..."
OPENAI_API_KEY=$(get_env_val "OPENAI_API_KEY")
SUPABASE_DB_URL=$(get_env_val "SUPABASE_DB_URL")
REDIS_URL=$(get_env_val "REDIS_URL")
QDRANT_URL=$(get_env_val "QDRANT_URL")
QDRANT_API_KEY=$(get_env_val "QDRANT_API_KEY")
if [[ -z "$QDRANT_API_KEY" ]]; then
  QDRANT_API_KEY=$(get_env_val "QDRANT_API")
fi
API_KEY=$(get_env_val "API_KEY")
HF_TOKEN=$(get_env_val "HF_TOKEN")
OPENROUTER_API_KEY=$(get_env_val "OPENROUTER_API_KEY")
LANGFUSE_PUBLIC_KEY=$(get_env_val "LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY=$(get_env_val "LANGFUSE_SECRET_KEY")
BASE_URL=$(get_env_val "BASE_URL")
GROQ_API_KEY=$(get_env_val "GROQ_API_KEY")

info "Starting Azure Resource provisioning via Bicep template..."
DEPLOYMENT_OUT=$(az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file "main.bicep" \
  --parameters \
    appName="$APP_NAME" \
    openaiApiKey="$OPENAI_API_KEY" \
    supabaseDbUrl="$SUPABASE_DB_URL" \
    redisUrl="$REDIS_URL" \
    qdrantUrl="$QDRANT_URL" \
    qdrantApiKey="$QDRANT_API_KEY" \
    apiKey="$API_KEY" \
    hfToken="$HF_TOKEN" \
    openrouterApiKey="$OPENROUTER_API_KEY" \
    langfusePublicKey="$LANGFUSE_PUBLIC_KEY" \
    langfuseSecretKey="$LANGFUSE_SECRET_KEY" \
    baseUrl="$BASE_URL" \
    groqApiKey="$GROQ_API_KEY" \
  --query "properties.outputs" \
  --output json)

ACR_LOGIN_SERVER=$(echo "$DEPLOYMENT_OUT" | jq -r '.registryLoginServer.value')
ACR_USERNAME=$(echo "$DEPLOYMENT_OUT" | jq -r '.registryUsername.value')
APP_FQDN=$(echo "$DEPLOYMENT_OUT" | jq -r '.containerAppFqdn.value')

success "Azure Resources Provisioned successfully!"
echo -e "
  ${BOLD}Azure Container Registry (ACR):${RESET}
    Login Server:  $ACR_LOGIN_SERVER
    Username:      $ACR_USERNAME

  ${BOLD}Container App FQDN:${RESET}
    URL:           https://$APP_FQDN
"

# Automatically update the GitHub Actions workflow file with the provisioned values
info "Updating GitHub Actions workflow configuration..."
python3 -c "
import sys
path = '../.github/workflows/azure-deploy.yml'
try:
    content = open(path).read()
    content = content.replace('<REGISTRY_LOGIN_SERVER>', '$ACR_LOGIN_SERVER')
    content = content.replace('<REGISTRY_USERNAME>', '$ACR_USERNAME')
    content = content.replace('<RESOURCE_GROUP>', '$RESOURCE_GROUP')
    content = content.replace('<CONTAINER_APP>', '$APP_NAME')
    open(path, 'w').write(content)
    print('[OK] Updated GitHub Actions workflow config successfully!')
except Exception as e:
    print(f'[WARN] Failed to update GitHub Actions workflow file: {e}')
"

# Guide user to create Service Principal for GitHub Actions
info "Creating Azure Service Principal for GitHub Actions CI/CD..."
SUBSCRIPTION_ID=$(az account show --query "id" -o tsv)

SP_JSON=$(az ad sp create-for-rbac \
  --name "cinemagic-github-actions-sp" \
  --role "contributor" \
  --scopes "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP" \
  --sdk-auth \
  --output json)

success "Service Principal Created!"
warn "Copy the following JSON block and add it as a secret named 'AZURE_CREDENTIALS' in your GitHub repository secrets:"
echo -e "${YELLOW}$SP_JSON${RESET}"

echo -e "\n${BOLD}Please configure the following secret in GitHub Repository Settings -> Secrets -> Actions:${RESET}"
echo -e "  1. ${BOLD}AZURE_CREDENTIALS${RESET} : (The JSON block printed above)"
echo -e "\nNote: All other variables (Registry, Resource Group, App Name) have been automatically configured in your workflow file!"
