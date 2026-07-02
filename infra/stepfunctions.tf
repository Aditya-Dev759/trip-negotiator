# Step Functions role (will use LabRole for now)
resource "aws_sfn_state_machine" "trip_negotiation" {
  name       = "${var.project_name}-negotiation-workflow"
  role_arn   = data.aws_iam_role.lab_role.arn
  definition = templatefile("${path.module}/statemachine.asl.json", {
    itinerary_arn  = aws_lambda_function.itinerary_agent.arn
    budget_arn     = aws_lambda_function.budget_agent.arn
    logistics_arn  = aws_lambda_function.logistics_agent.arn
    booking_arn    = aws_lambda_function.booking_agent.arn
    supervisor_arn = aws_lambda_function.supervisor.arn
  })

  # Operational Excellence: X-Ray gives an end-to-end trace of a single
  # negotiation across all 4-5 Lambda invocations per round, not just each
  # function's isolated logs -- useful for spotting which agent is the
  # actual bottleneck in a slow round.
  tracing_configuration {
    enabled = true
  }

  depends_on = [
    aws_lambda_function.itinerary_agent,
    aws_lambda_function.budget_agent,
    aws_lambda_function.logistics_agent,
    aws_lambda_function.booking_agent,
    aws_lambda_function.supervisor,
  ]

  tags = local.common_tags
}

output "state_machine_arn" {
  value = aws_sfn_state_machine.trip_negotiation.arn
}
