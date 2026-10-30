output "alb_dns_name" {
  value = aws_lb.app.dns_name
}

output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "s3_bucket" {
  value = aws_s3_bucket.docs.bucket
}

output "dynamodb_table" {
  value = aws_dynamodb_table.chunks.name
}
