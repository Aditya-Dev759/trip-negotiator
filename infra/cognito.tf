# Cognito user pool + JWT authorizer for API Gateway, now wired end-to-end:
# the frontend (frontend/src/lib/auth.ts, AuthContext.tsx, LoginForm.tsx)
# implements real sign-up/confirm/sign-in/sign-out against this pool using
# amazon-cognito-identity-js (SRP auth, no Cognito Hosted UI domain needed),
# and frontend/src/lib/api.ts attaches the resulting ID token as a Bearer
# Authorization header on every request. var.enable_auth now defaults to
# true as a result -- see variables.tf.

resource "aws_cognito_user_pool" "trip_users" {
  name = "${var.project_name}-user-pool"

  # Sign in/up by email rather than a separate username -- simpler for a
  # single-purpose travel-planning app with no need for display handles.
  username_attributes     = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_symbols   = false
    require_uppercase = true
  }

  # Cognito's own default email sending (no SES setup needed) delivers the
  # sign-up verification code -- fine for course-project-scale usage, has a
  # daily sending cap that would need SES for anything beyond that.
  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
    email_subject        = "Your TripNegotiator verification code"
    email_message        = "Your TripNegotiator verification code is {####}"
  }

  schema {
    name                = "email"
    attribute_data_type = "String"
    required            = true
    mutable             = true
  }

  tags = local.common_tags
}

# Server-side / testing client (client secret is fine here -- it's never
# shipped to a browser).
resource "aws_cognito_user_pool_client" "trip_api_client" {
  name            = "${var.project_name}-api-client"
  user_pool_id    = aws_cognito_user_pool.trip_users.id
  generate_secret = true

  explicit_auth_flows = [
    "ADMIN_NO_SRP_AUTH",
    "USER_PASSWORD_AUTH",
  ]
}

# Public (no-secret) client for the Next.js SPA. Browser apps can't keep a
# client secret confidential, so Cognito app clients meant for frontend use
# must be created with generate_secret = false -- using trip_api_client's
# secret-bearing client from the browser would leak the secret in every
# request. explicit_auth_flows here enables the SRP flow
# (ALLOW_USER_SRP_AUTH) that amazon-cognito-identity-js's
# CognitoUser.authenticateUser() performs by default -- the password itself
# never goes over the wire, only a zero-knowledge proof derived from it.
resource "aws_cognito_user_pool_client" "spa_client" {
  name            = "${var.project_name}-spa-client"
  user_pool_id    = aws_cognito_user_pool.trip_users.id
  generate_secret = false

  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  access_token_validity  = 24
  id_token_validity      = 24
  refresh_token_validity = 30

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }
}

resource "aws_apigatewayv2_authorizer" "cognito" {
  count            = var.enable_auth ? 1 : 0
  api_id           = aws_apigatewayv2_api.trip_api.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "${var.project_name}-cognito-authorizer"

  jwt_configuration {
    audience = [aws_cognito_user_pool_client.spa_client.id]
    issuer   = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.trip_users.id}"
  }
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.trip_users.id
}

output "cognito_spa_client_id" {
  value = aws_cognito_user_pool_client.spa_client.id
}
