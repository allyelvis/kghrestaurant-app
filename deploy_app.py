import os
import subprocess
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.web import WebSiteManagementClient
from azure.mgmt.containerregistry import ContainerRegistryManagementClient
from azure.mgmt.sql import SqlManagementClient
from azure.mgmt.keyvault import KeyVaultManagementClient
from azure.mgmt.containerservice import ContainerServiceClient
from azure.mgmt.mysql_flexibleservers import MySQLManagementClient

# Configuration
SUBSCRIPTION_ID = "your_subscription_id"
RESOURCE_GROUP = "kghrestaurant_group"
LOCATION = "eastus"
APP_NAME = "AENZ"
CONTAINER_APP_NAME = "byzapp"
MYSQL_SERVER_NAME = "aenz-server"
SQL_SERVER_NAME = "poserver"
KEY_VAULT_NAME = "Kgvlt"
ACR_NAME = "kghrestaurantacr"
AKS_CLUSTER_NAME = "Azurcont"
GIT_REPO = "https://github.com/your-repo/kghrestaurant-app.git"
ADMIN_PASSWORD = "P@ssw0rd1234!"

# Initialize clients
credential = DefaultAzureCredential()
resource_client = ResourceManagementClient(credential, SUBSCRIPTION_ID)
web_client = WebSiteManagementClient(credential, SUBSCRIPTION_ID)
acr_client = ContainerRegistryManagementClient(credential, SUBSCRIPTION_ID)
sql_client = SqlManagementClient(credential, SUBSCRIPTION_ID)
keyvault_client = KeyVaultManagementClient(credential, SUBSCRIPTION_ID)
aks_client = ContainerServiceClient(credential, SUBSCRIPTION_ID)
mysql_client = MySQLManagementClient(credential, SUBSCRIPTION_ID)

# Step 1: Create Resource Group
def create_resource_group():
    print("Creating resource group...")
    resource_client.resource_groups.create_or_update(
        RESOURCE_GROUP, {"location": LOCATION}
    )

# Step 2: Create App Service
def create_app_service():
    print("Creating App Service...")
    web_client.app_service_plans.begin_create_or_update(
        RESOURCE_GROUP,
        f"ASP-{RESOURCE_GROUP}",
        {
            "location": LOCATION,
            "sku": {"name": "P1v2", "tier": "PremiumV2", "size": "P1"},
            "reserved": True,
        },
    )
    web_client.web_apps.begin_create_or_update(
        RESOURCE_GROUP,
        APP_NAME,
        {
            "location": LOCATION,
            "server_farm_id": f"ASP-{RESOURCE_GROUP}",
            "site_config": {"linux_fx_version": "NODE|18-lts"},
        },
    )

# Step 3: Create MySQL Flexible Server
def create_mysql_server():
    print("Creating MySQL Flexible Server...")
    mysql_client.servers.begin_create(
        RESOURCE_GROUP,
        MYSQL_SERVER_NAME,
        {
            "location": LOCATION,
            "administrator_login": "mysqladmin",
            "administrator_login_password": ADMIN_PASSWORD,
            "sku": {"name": "Standard_B1ms"},
        },
    )

# Step 4: Create SQL Server
def create_sql_server():
    print("Creating SQL Server...")
    sql_client.servers.begin_create_or_update(
        RESOURCE_GROUP,
        SQL_SERVER_NAME,
        {
            "location": LOCATION,
            "administrator_login": "sqladmin",
            "administrator_login_password": ADMIN_PASSWORD,
        },
    )

# Step 5: Create Key Vault
def create_key_vault():
    print("Creating Key Vault...")
    keyvault_client.vaults.begin_create_or_update(
        RESOURCE_GROUP,
        KEY_VAULT_NAME,
        {
            "location": LOCATION,
            "properties": {
                "sku": {"family": "A", "name": "standard"},
                "tenant_id": credential._client_id,  # Get tenant ID dynamically
            },
        },
    )

# Step 6: Create Azure Container Registry
def create_acr():
    print("Creating Azure Container Registry...")
    acr_client.registries.begin_create(
        RESOURCE_GROUP,
        ACR_NAME,
        {
            "location": LOCATION,
            "sku": {"name": "Basic"},
            "admin_user_enabled": True,
        },
    )

# Step 7: Create AKS Cluster
def create_aks_cluster():
    print("Creating AKS Cluster...")
    aks_client.managed_clusters.begin_create_or_update(
        RESOURCE_GROUP,
        AKS_CLUSTER_NAME,
        {
            "location": LOCATION,
            "dns_prefix": f"{AKS_CLUSTER_NAME}-dns",
            "agent_pool_profiles": [
                {"name": "nodepool1", "count": 1, "vm_size": "Standard_DS2_v2"}
            ],
            "service_principal_profile": {
                "client_id": credential._client_id,
                "secret": credential._client_secret,
            },
        },
    )

# Step 8: Clone and Build Application
def clone_and_build_app():
    print("Cloning application repository...")
    subprocess.run(["git", "clone", GIT_REPO])
    os.chdir("kghrestaurant-app")
    print("Installing dependencies...")
    subprocess.run(["npm", "install"])
    print("Building application...")
    subprocess.run(["npm", "run", "build"])

# Step 9: Create Docker Image
def create_docker_image():
    print("Creating Docker image...")
    with open("Dockerfile", "w") as dockerfile:
        dockerfile.write(
            """
            FROM node:18-alpine AS builder
            WORKDIR /app
            COPY package.json ./
            RUN npm install
            COPY . .
            RUN npm run build
            FROM node:18-alpine
            WORKDIR /app
            COPY --from=builder /app .
            CMD ["npm", "start"]
            """
        )
    subprocess.run(["docker", "build", "-t", f"{ACR_NAME}.azurecr.io/kghrestaurant-app:latest", "."])
    print("Pushing Docker image to ACR...")
    subprocess.run(["az", "acr", "login", "--name", ACR_NAME])
    subprocess.run(["docker", "push", f"{ACR_NAME}.azurecr.io/kghrestaurant-app:latest"])

# Step 10: Deploy to AKS
def deploy_to_aks():
    print("Deploying application to AKS...")
    with open("k8s-deployment.yaml", "w") as k8s_file:
        k8s_file.write(
            f"""
            apiVersion: apps/v1
            kind: Deployment
            metadata:
              name: kghrestaurant-app
            spec:
              replicas: 3
              selector:
                matchLabels:
                  app: kghrestaurant-app
              template:
                metadata:
                  labels:
                    app: kghrestaurant-app
                spec:
                  containers:
                  - name: kghrestaurant-app
                    image: {ACR_NAME}.azurecr.io/kghrestaurant-app:latest
                    ports:
                    - containerPort: 80
            ---
            apiVersion: v1
            kind: Service
            metadata:
              name: kghrestaurant-app-service
            spec:
              selector:
                app: kghrestaurant-app
              ports:
                - protocol: TCP
                  port: 80
                  targetPort: 80
              type: LoadBalancer
            """
        )
    subprocess.run(["kubectl", "apply", "-f", "k8s-deployment.yaml"])

# Main Execution
if __name__ == "__main__":
    create_resource_group()
    create_app_service()
    create_mysql_server()
    create_sql_server()
    create_key_vault()
    create_acr()
    create_aks_cluster()
    clone_and_build_app()
    create_docker_image()
    deploy_to_aks()
    print("All steps completed successfully!")
