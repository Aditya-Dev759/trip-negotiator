# Operational Excellence pillar: alarms + a place for them to notify, so
# failures surface without someone having to go looking in CloudWatch Logs.
# Previously there were zero aws_cloudwatch_metric_alarm resources anywhere
# in this project -- API Gateway had an access-log group, but nothing
# actually watched Lambda error rates, Lambda duration approaching timeout,
# or Step Functions execution failures.

resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-alerts"
  tags = local.common_tags
}

resource "aws_sns_topic_subscription" "alerts_email" {
  count     = var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

locals {
  # One alarm pair (errors + duration) per Lambda, driven off a map so
  # adding a function later just means adding a map entry instead of
  # copy-pasting two more resource blocks.
  lambda_functions = {
    api             = aws_lambda_function.api
    itinerary_agent = aws_lambda_function.itinerary_agent
    budget_agent    = aws_lambda_function.budget_agent
    logistics_agent = aws_lambda_function.logistics_agent
    booking_agent   = aws_lambda_function.booking_agent
    supervisor      = aws_lambda_function.supervisor
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  for_each = local.lambda_functions

  alarm_name          = "${var.project_name}-${each.key}-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods   = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_description   = "One or more invocation errors in ${each.value.function_name} in the last 5 minutes"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]

  dimensions = {
    FunctionName = each.value.function_name
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  for_each = local.lambda_functions

  alarm_name          = "${var.project_name}-${each.key}-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods   = 1
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "p95"
  # Alarm at 80% of the function's configured timeout -- catches "about to
  # start timing out" before it actually does.
  threshold          = each.value.timeout * 1000 * 0.8
  treat_missing_data = "notBreaching"
  alarm_description  = "p95 duration for ${each.value.function_name} is approaching its ${each.value.timeout}s timeout"
  alarm_actions      = [aws_sns_topic.alerts.arn]

  dimensions = {
    FunctionName = each.value.function_name
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "negotiation_failures" {
  alarm_name          = "${var.project_name}-negotiation-execution-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods   = 1
  metric_name         = "ExecutionsFailed"
  namespace           = "AWS/States"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_description   = "A trip negotiation Step Functions execution failed (exhausted its Retry/Catch and hit HandleError)"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    StateMachineArn = aws_sfn_state_machine.trip_negotiation.arn
  }

  tags = local.common_tags
}

output "alerts_topic_arn" {
  value       = aws_sns_topic.alerts.arn
  description = "Subscribe additional endpoints (Slack webhook via Chatbot, PagerDuty, etc.) to this topic"
}
