variable "location" {
  description = "Azure region for all resources."
  type        = string
  default     = "eastus"
}

variable "resource_group_name" {
  description = "Name of the Azure resource group."
  type        = string
  default     = "rg-docuquery-platform-demo"
}

variable "cluster_name" {
  description = "Name of the AKS cluster."
  type        = string
  default     = "aks-docuquery-demo"
}

variable "dns_prefix" {
  description = "DNS prefix assigned to the AKS API server."
  type        = string
  default     = "docuquery-demo"
}

variable "node_count" {
  description = "Number of nodes in the default AKS node pool."
  type        = number
  default     = 1

  validation {
    condition     = var.node_count >= 1 && var.node_count <= 5
    error_message = "node_count must be between 1 and 5."
  }
}

variable "node_vm_size" {
  description = "Azure VM size for the default AKS node pool."
  type        = string
  default     = "Standard_B2s"
}

variable "environment" {
  description = "Environment tag applied to Azure resources."
  type        = string
  default     = "demo"
}
