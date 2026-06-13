output "resource_group_name" {
  description = "Name of the provisioned Azure resource group."
  value       = azurerm_resource_group.docuquery.name
}

output "cluster_name" {
  description = "Name of the provisioned AKS cluster."
  value       = azurerm_kubernetes_cluster.docuquery.name
}

output "kube_config_command" {
  description = "Azure CLI command that writes AKS credentials to the current kubeconfig."
  value       = "az aks get-credentials --resource-group ${azurerm_resource_group.docuquery.name} --name ${azurerm_kubernetes_cluster.docuquery.name} --overwrite-existing"
}
