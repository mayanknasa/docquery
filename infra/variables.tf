variable "region" {
  type    = string
  default = "us-east-1"
}

variable "project" {
  type    = string
  default = "docquery"
}

variable "image_tag" {
  type    = string
  default = "latest"
}

variable "container_port" {
  type    = number
  default = 8000
}

variable "desired_count" {
  type    = number
  default = 1
}

variable "llm_provider" {
  type        = string
  default     = "openai"
  description = "openai for real answers, mock for a free offline demo"
}

variable "openai_api_key" {
  type      = string
  default   = ""
  sensitive = true
}

variable "api_key" {
  type        = string
  default     = ""
  sensitive   = true
  description = "Clients must send this in the X-API-Key header. Empty disables the check."
}
