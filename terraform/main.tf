provider "aws" {
  region = var.aws_region
}

resource "aws_iam_role" "lambda_exec_role" {
  name = "lambda_exec_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole",
      Effect = "Allow",
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_dynamo" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess"
}

resource "aws_iam_role_policy_attachment" "lambda_comprehend" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/ComprehendReadOnly"
}

resource "aws_iam_role_policy_attachment" "lambda_sns" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSNSFullAccess"
}

resource "aws_lambda_function" "message_processor" {
  function_name = "MessageProcessor"
  role          = aws_iam_role.lambda_exec_role.arn
  handler       = "messageProcessor.lambda_handler"
  runtime       = "python3.9"
  filename         = "${path.module}/lambda/messageProcessor.zip"
  source_code_hash = filebase64sha256("${path.module}/lambda/messageProcessor.zip")

  environment {
    variables = {
      TELEGRAM_BOT_TOKEN = var.telegram_bot_token
    }
  }
}

resource "aws_dynamodb_table" "flagged_messages" {
  name         = "FlaggedMessages"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "MessageID"

  attribute {
    name = "MessageID"
    type = "S"
  }
}

resource "aws_dynamodb_table" "user_flag_counts" {
  name         = "UserFlagCounts"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "UserID"
  range_key    = "GroupName"

  attribute {
    name = "UserID"
    type = "S"
  }

  attribute {
    name = "GroupName"
    type = "S"
  }
}

resource "aws_sns_topic" "admin_alerts" {
  name = "AdminAlerts"
}