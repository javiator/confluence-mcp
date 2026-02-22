terraform {
  backend "s3" {
    bucket  = "tenant-management-tf-state-383226947124"
    key     = "confluence-mcp/terraform.tfstate"
    region  = "us-east-1"
    encrypt = true
  }
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}
