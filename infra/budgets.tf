# Cost Optimization guardrail. README/PROGRESS.md have always *claimed* a
# <$5/month or <$5-total cost target for this project, but nothing actually
# enforced or alerted on that -- it was just an estimate in a markdown file.
#
# NOTE: AWS Academy Learner Lab's LabRole commonly does NOT include
# budgets:* permissions (Budgets is an account-level, not resource-level,
# API and Learner Lab IAM policies are intentionally locked down). If
# `terraform apply` fails on this resource with an AccessDenied error, that
# is the expected Learner Lab constraint the assignment explicitly says to
# document rather than work around: in a production/non-Lab account this
# budget would page the team before the Learner Lab's own 45-credit ceiling
# does.
#
# AWS Budgets requires at least one subscriber per notification block, so
# this whole resource is skipped (not just the subscriber list) when
# alert_email isn't set, rather than deploying a budget nothing can notify.
resource "aws_budgets_budget" "monthly_cost_guardrail" {
  count = var.alert_email != "" ? 1 : 0

  name         = "${var.project_name}-monthly-guardrail"
  budget_type  = "COST"
  limit_amount = "5"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }
}
