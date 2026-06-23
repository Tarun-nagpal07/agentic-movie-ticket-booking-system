param location string = resourceGroup().location
param appName string = 'cinemagic-app'
param environmentName string = 'cinemagic-env'
param registryName string = 'cinemagicregistry${uniqueString(resourceGroup().id)}'
param containerImage string = 'mcr.microsoft.com/azuredocs/aci-helloworld:latest'

@secure()
param openaiApiKey string = ''
@secure()
param supabaseDbUrl string = ''
@secure()
param redisUrl string = ''
@secure()
param qdrantUrl string = ''
@secure()
param qdrantApiKey string = ''
@secure()
param apiKey string = ''
@secure()
param hfToken string = ''
@secure()
param openrouterApiKey string = ''
param langfusePublicKey string = ''
@secure()
param langfuseSecretKey string = ''
param baseUrl string = ''
@secure()
param groqApiKey string = ''
@secure()
param tmdbApiKey string = ''

// Container Registry
resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: registryName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

// Log Analytics Workspace
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: '${appName}-logs'
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// Container Apps Environment
resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// Container App
resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8501
        allowInsecure: false
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
      }
      secrets: [
        {
          name: 'registry-password'
          value: registry.listCredentials().passwords[0].value
        }
        {
          name: 'openai-api-key'
          value: openaiApiKey
        }
        {
          name: 'supabase-db-url'
          value: supabaseDbUrl
        }
        {
          name: 'redis-url'
          value: redisUrl
        }
        {
          name: 'qdrant-url'
          value: qdrantUrl
        }
        {
          name: 'qdrant-api-key'
          value: qdrantApiKey
        }
        {
          name: 'api-key'
          value: apiKey
        }
        {
          name: 'hf-token'
          value: hfToken
        }
        {
          name: 'openrouter-api-key'
          value: openrouterApiKey
        }
        {
          name: 'langfuse-secret-key'
          value: langfuseSecretKey
        }
        {
          name: 'groq-api-key'
          value: groqApiKey
        }
        {
          name: 'tmdb-api-key'
          value: tmdbApiKey
        }
      ]
      registries: [
        {
          server: registry.properties.loginServer
          username: registry.name
          passwordSecretRef: 'registry-password'
        }
      ]
    }
    template: {
      containers: [
        {
          name: appName
          image: containerImage
          resources: {
            cpu: json('0.5')
            memory: '1.0Gi'
          }
          env: [
            {
              name: 'OPENAI_API_KEY'
              secretRef: 'openai-api-key'
            }
            {
              name: 'SUPABASE_DB_URL'
              secretRef: 'supabase-db-url'
            }
            {
              name: 'REDIS_URL'
              secretRef: 'redis-url'
            }
            {
              name: 'QDRANT_URL'
              secretRef: 'qdrant-url'
            }
            {
              name: 'QDRANT_API_KEY'
              secretRef: 'qdrant-api-key'
            }
            {
              name: 'API_KEY'
              secretRef: 'api-key'
            }
            {
              name: 'HF_TOKEN'
              secretRef: 'hf-token'
            }
            {
              name: 'OPENROUTER_API_KEY'
              secretRef: 'openrouter-api-key'
            }
            {
              name: 'LANGFUSE_PUBLIC_KEY'
              value: langfusePublicKey
            }
            {
              name: 'LANGFUSE_SECRET_KEY'
              secretRef: 'langfuse-secret-key'
            }
            {
              name: 'BASE_URL'
              value: baseUrl
            }
            {
              name: 'GROQ_API_KEY'
              secretRef: 'groq-api-key'
            }
            {
              name: 'TMDB_API_KEY'
              secretRef: 'tmdb-api-key'
            }
            {
              name: 'PORT'
              value: '8501'
            }
          ]
        }
      ]
    }
  }
}

output registryLoginServer string = registry.properties.loginServer
output registryUsername string = registry.name
output containerAppFqdn string = containerApp.properties.configuration.ingress.fqdn
