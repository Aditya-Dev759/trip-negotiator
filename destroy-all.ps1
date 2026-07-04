# destroy-all.ps1
#
# Manually tears down every real AWS resource this project creates. Written
# because infra/ uses backend "local" and this project has been applied both
# from a developer machine AND from GitHub Actions (a separate, ephemeral
# runner) -- each apply's Terraform state only ever exists on the machine
# that ran it, so there is no single state file anywhere that reliably
# describes everything currently live. `terraform destroy` from any one
# machine can only destroy what that machine's own state file knows about,
# which may be empty even while real resources exist in AWS. This script
# deletes by resource name directly via the AWS CLI instead, so it works
# regardless of which state (if any) is accurate.
#
# Safe to re-run: every step below tolerates "already deleted / not found"
# errors and just moves on, so run this as many times as you want.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File destroy-all.ps1
# or, from inside PowerShell:
#   .\destroy-all.ps1
#
# Pass -Force (or run with $env:CI = "true", which GitHub Actions sets
# automatically) to skip the interactive confirmation prompt -- there's no
# terminal attached to type "yes" into from a CI runner, and Read-Host would
# otherwise just hang until the job times out. Used by
# .github/workflows/destroy.yml, which gates on its own separate typed
# confirmation in the workflow_dispatch input before ever reaching this
# script, so skipping the prompt here isn't removing a safety check -- it's
# moving it to the one place that's actually interactive (the Actions "Run
# workflow" form).

param(
    [switch]$Force
)

$ErrorActionPreference = "Continue"

Write-Host "=== TripNegotiator: destroying all AWS resources ===" -ForegroundColor Yellow
Write-Host "Uses whatever AWS credentials are currently active (aws configure / Learner Lab AWS Details)." -ForegroundColor Yellow

if (-not $Force -and $env:CI -ne "true") {
    $confirm = Read-Host "Type 'yes' to continue"
    if ($confirm -ne "yes") {
        Write-Host "Aborted."
        exit 0
    }
} else {
    Write-Host "Running non-interactively (-Force or CI=true) -- skipping confirmation prompt." -ForegroundColor Yellow
}

function Step($name, [scriptblock]$action) {
    Write-Host ""
    Write-Host "--- $name ---" -ForegroundColor Cyan
    try {
        & $action
    } catch {
        Write-Host "  (non-fatal) $($_.Exception.Message)" -ForegroundColor DarkYellow
    }
}

# 1. Step Functions state machine
Step "Step Functions state machine" {
    aws stepfunctions delete-state-machine --state-machine-arn arn:aws:states:us-east-1:260318502395:stateMachine:tripnegotiator-negotiation-workflow 2>&1 | Out-String | Write-Host
}

# 2. CloudWatch alarms (2 per Lambda x 6 Lambdas + 1 Step Functions alarm)
Step "CloudWatch alarms" {
    aws cloudwatch delete-alarms --alarm-names `
        tripnegotiator-api-errors tripnegotiator-api-duration `
        tripnegotiator-itinerary_agent-errors tripnegotiator-itinerary_agent-duration `
        tripnegotiator-budget_agent-errors tripnegotiator-budget_agent-duration `
        tripnegotiator-logistics_agent-errors tripnegotiator-logistics_agent-duration `
        tripnegotiator-booking_agent-errors tripnegotiator-booking_agent-duration `
        tripnegotiator-supervisor-errors tripnegotiator-supervisor-duration `
        tripnegotiator-negotiation-execution-failures 2>&1 | Out-String | Write-Host
}

# 3. SNS topic
Step "SNS alerts topic" {
    aws sns delete-topic --topic-arn arn:aws:sns:us-east-1:260318502395:tripnegotiator-alerts 2>&1 | Out-String | Write-Host
}

# 4. API Gateway HTTP API (cascades: routes, integrations, stage, authorizer)
Step "API Gateway HTTP API" {
    $apis = aws apigatewayv2 get-apis --query "Items[?Name=='tripnegotiator-http-api'].ApiId" --output text
    if ($apis) {
        foreach ($apiId in ($apis -split "\s+")) {
            if ($apiId) {
                Write-Host "  deleting API $apiId"
                aws apigatewayv2 delete-api --api-id $apiId 2>&1 | Out-String | Write-Host
            }
        }
    } else {
        Write-Host "  no matching API found"
    }
}

# 5. Lambda functions
Step "Lambda functions" {
    foreach ($fn in @(
        "tripnegotiator-api",
        "tripnegotiator-itinerary-agent",
        "tripnegotiator-budget-agent",
        "tripnegotiator-logistics-agent",
        "tripnegotiator-booking-agent",
        "tripnegotiator-supervisor"
    )) {
        Write-Host "  deleting $fn"
        aws lambda delete-function --function-name $fn 2>&1 | Out-String | Write-Host
    }
}

# 6. Cognito user pool (deletes both app clients with it)
Step "Cognito user pool" {
    $pools = aws cognito-idp list-user-pools --max-results 60 --query "UserPools[?Name=='tripnegotiator-user-pool'].Id" --output text
    if ($pools) {
        foreach ($poolId in ($pools -split "\s+")) {
            if ($poolId) {
                Write-Host "  deleting user pool $poolId"
                aws cognito-idp delete-user-pool --user-pool-id $poolId 2>&1 | Out-String | Write-Host
            }
        }
    } else {
        Write-Host "  no matching user pool found"
    }
}

# 7. DynamoDB table
Step "DynamoDB table" {
    aws dynamodb delete-table --table-name tripnegotiator-negotiations 2>&1 | Out-String | Write-Host
}

# 8. S3 buckets (both are versioned -- must purge all versions + delete
# markers before the bucket itself can be deleted; plain `aws s3 rm` only
# adds delete markers on a versioned bucket, it doesn't remove old versions)
Step "S3 buckets (purge versions + delete)" {
    $accountId = aws sts get-caller-identity --query Account --output text
    if (-not $accountId) { $accountId = "260318502395" }
    $buckets = @("tripnegotiator-frontend-$accountId", "tripnegotiator-data-$accountId")

    python -c "
import boto3, sys
s3 = boto3.client('s3')
buckets = sys.argv[1:]
for b in buckets:
    try:
        paginator = s3.get_paginator('list_object_versions')
        for page in paginator.paginate(Bucket=b):
            objs = [{'Key': v['Key'], 'VersionId': v['VersionId']} for v in page.get('Versions', [])]
            objs += [{'Key': v['Key'], 'VersionId': v['VersionId']} for v in page.get('DeleteMarkers', [])]
            if objs:
                s3.delete_objects(Bucket=b, Delete={'Objects': objs})
                print(f'{b}: purged {len(objs)} versions/markers')
    except Exception as e:
        print(f'{b}: {e}')
" @buckets

    foreach ($bucket in $buckets) {
        Write-Host "  deleting bucket $bucket"
        aws s3api delete-bucket --bucket $bucket 2>&1 | Out-String | Write-Host
    }
}

# 9. ECR repository (force removes any remaining images)
Step "ECR repository" {
    aws ecr delete-repository --repository-name tripnegotiator-lambda --force 2>&1 | Out-String | Write-Host
}

# 10. SSM parameter
Step "SSM parameter (Groq key)" {
    aws ssm delete-parameter --name /tripnegotiator/groq-key 2>&1 | Out-String | Write-Host
}

# 11. CloudWatch log groups (API Gateway access logs + any Lambda log groups
# that exist because a function was actually invoked at least once -- these
# are auto-created by AWS on first invoke, not created by Terraform)
Step "CloudWatch log groups" {
    foreach ($lg in @(
        "/aws/apigateway/tripnegotiator-http-api",
        "/aws/lambda/tripnegotiator-api",
        "/aws/lambda/tripnegotiator-itinerary-agent",
        "/aws/lambda/tripnegotiator-budget-agent",
        "/aws/lambda/tripnegotiator-logistics-agent",
        "/aws/lambda/tripnegotiator-booking-agent",
        "/aws/lambda/tripnegotiator-supervisor"
    )) {
        Write-Host "  deleting log group $lg"
        aws logs delete-log-group --log-group-name $lg 2>&1 | Out-String | Write-Host
    }
}

# 12. AWS Budget + SNS email subscription -- only created when
# TF_VAR_alert_email / var.alert_email is set (infra/budgets.tf,
# infra/monitoring.tf both gate on it with count = var.alert_email != "" ? 1 : 0).
# Uncomment and fill in if you ever set that variable:
# Step "AWS Budget" {
#     aws budgets delete-budget --account-id $accountId --budget-name tripnegotiator-monthly-guardrail 2>&1 | Out-String | Write-Host
# }

Write-Host ""
Write-Host "=== Done. Some 'not found' messages above are expected (resources already gone or never created) and safe to ignore. ===" -ForegroundColor Green
