output "lambda_arn" {
  value = aws_lambda_function.message_processor.arn
}

output "sns_topic_arn" {
  value = aws_sns_topic.admin_alerts.arn
}