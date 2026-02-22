# Terraform Backend Configuration
# This file configures remote state storage for Terraform

# AWS S3 Backend (uncomment for AWS)
# terraform {
#   backend "s3" {
#     bucket         = "agent-guru-terraform-state"
#     key            = "reasoning-engine/terraform.tfstate"
#     region         = "us-east-1"
#     encrypt        = true
#     dynamodb_table = "terraform-state-lock"
#   }
# }

# Google Cloud Storage Backend (uncomment for GCP)
# terraform {
#   backend "gcs" {
#     bucket  = "agent-guru-terraform-state"
#     prefix  = "reasoning-engine"
#   }
# }

# Azure Storage Backend (uncomment for Azure)
# terraform {
#   backend "azurerm" {
#     resource_group_name  = "agent-guru-terraform"
#     storage_account_name = "agentguruterraform"
#     container_name       = "tfstate"
#     key                  = "reasoning-engine.terraform.tfstate"
#   }
# }

# Local Backend (for development/testing only)
terraform {
  backend "local" {
    path = "terraform.tfstate"
  }
}
