locals {
  common_tags = {
    application = "docuquery"
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "azurerm_resource_group" "docuquery" {
  name     = var.resource_group_name
  location = var.location
  tags     = local.common_tags
}

resource "azurerm_kubernetes_cluster" "docuquery" {
  name                = var.cluster_name
  location            = azurerm_resource_group.docuquery.location
  resource_group_name = azurerm_resource_group.docuquery.name
  dns_prefix          = var.dns_prefix

  default_node_pool {
    name            = "system"
    node_count      = var.node_count
    vm_size         = var.node_vm_size
    os_disk_size_gb = 30
    type            = "VirtualMachineScaleSets"
  }

  identity {
    type = "SystemAssigned"
  }

  network_profile {
    network_plugin    = "azure"
    load_balancer_sku = "standard"
  }

  role_based_access_control_enabled = true
  local_account_disabled            = false

  tags = local.common_tags
}
