<#
.SYNOPSIS
  Full teardown of all "tripnegotiator" AWS resources.

.DESCRIPTION
  infra/ uses Terraform's local backend, and every CI run's state file only
  ever lives on the ephemeral GitHub Actions runner that created it — gone
  the moment that job ends. That means `terraform destroy` almost never has
  an accurate picture of what's actually live in AWS (see the
  RepositoryAlreadyExistsException / ResourceInUseException errors this has
  already produced). This script sidesteps Terraform state entirely: it
  discovers resources directly from AWS by name prefix and deletes them with
  the AWS CLI, in dependency-safe order, with force-delete behavior where AWS
  otherwise refuses (non-empty ECR repos, non-empty S3 buckets, protected
  DynamoDB tables).

  Scope: S3 (frontend bucket), Lambda functions + their log groups, the HTTP
  API, the DynamoDB table, remaining CloudWatch log groups, the ECR repo,
  the Cognito user pool (+ custom domain if any), and Step Functions state
  machines if present. IAM is intentionally NOT touched — this project only
  uses the pre-existing AWS Academy `LabRole`, no custom roles are created.

  If infra/*.tf defines other resource types not listed above (SQS,
  EventBridge, etc.), add a matching block — the pattern is the same for
  every service: list by prefix, delete by name/ARN.

.PARAMETER Yes
  Actually delete resources. Without this, the script only prints what it
  would do (dry run) and changes nothing.

.PARAMETER Force
  Skip the interactive typed confirmation. Combine with -Yes for
  non-interactive use.

.EXAMPLE
  .\destroy-all.ps1
  Dry run — lists what would be deleted, deletes nothing.

.EXAMPLE
  .\destroy-all.ps1 -Yes
  Deletes everything matching the prefix, after you type the prefix to confirm.

.EXAMPLE
  .\destroy-all.ps1 -Yes -Force
  Deletes everything with no prompt.

.NOTES
  Requires AWS CLI v2 and valid credentials in the environment (same vars as
  the GitHub Actions workflow: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY /
  AWS_SESSION_TOKEN) or a working default profile.
#>

param(
    [switch]$Yes,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$Prefix = "tripnegotiator"
$Region = if ($env:AWS_REGION) { $env:AWS_REGION } else { "us-east-1" }
$DryRun = -not $Yes

function Write-Section($name) {
    Write-Host ""
    Write-Host "== $name ==" -ForegroundColor Cyan
}

function Invoke-Action {
    param(
        [string]$Description,
        [scriptblock]$Action
    )
    if ($DryRun) {
        Write-Host "  [DRY RUN] $Description" -ForegroundColor Yellow
    } else {
        Write-Host "  + $Description" -ForegroundColor Green
        & $Action | Out-Null
    }
}

# Wraps a listing call so a missing service/permission/region issue just
# means "treat as empty" instead of killing the whole script.
function Get-AwsJson {
    param([string]$CliCommand)
    try {
        $raw = Invoke-Expression "$CliCommand --output json" 2>$null
        if (-not $raw) { return $null }
        return $raw | ConvertFrom-Json
    } catch {
        return $null
    }
}

Write-Host "Region: $Region"
Write-Host "Mode:   $(if ($DryRun) { 'DRY RUN (no changes)' } else { 'LIVE - will delete resources' })"

if (-not $DryRun -and -not $Force) {
    $confirm = Read-Host "Type '$Prefix' to confirm permanent deletion of all matching AWS resources"
    if ($confirm -ne $Prefix) {
        Write-Host "Confirmation did not match. Aborting."
        exit 1
    }
}

### 1. S3 buckets ##############################################################
Write-Section "S3 buckets"
$buckets = (Get-AwsJson "aws s3api list-buckets").Buckets | Where-Object { $_.Name -like "$Prefix*" }
if ($buckets) {
    foreach ($b in $buckets) {
        $bucket = $b.Name
        Write-Host "Bucket: $bucket"
        Invoke-Action "aws s3 rm s3://$bucket --recursive" { aws s3 rm "s3://$bucket" --recursive }

        $versioning = (Get-AwsJson "aws s3api get-bucket-versioning --bucket $bucket").Status
        if ($versioning -eq "Enabled" -or $versioning -eq "Suspended") {
            if ($DryRun) {
                Write-Host "  [DRY RUN] would purge remaining object versions and delete markers in $bucket" -ForegroundColor Yellow
            } else {
                $versions = Get-AwsJson "aws s3api list-object-versions --bucket $bucket"
                if ($versions.Versions) {
                    $payload = @{ Objects = $versions.Versions | ForEach-Object { @{ Key = $_.Key; VersionId = $_.VersionId } } } | ConvertTo-Json -Depth 5
                    $tmp = New-TemporaryFile
                    Set-Content -Path $tmp -Value $payload -Encoding utf8
                    aws s3api delete-objects --bucket $bucket --delete "file://$tmp" | Out-Null
                    Remove-Item $tmp -Force
                }
                if ($versions.DeleteMarkers) {
                    $payload2 = @{ Objects = $versions.DeleteMarkers | ForEach-Object { @{ Key = $_.Key; VersionId = $_.VersionId } } } | ConvertTo-Json -Depth 5
                    $tmp2 = New-TemporaryFile
                    Set-Content -Path $tmp2 -Value $payload2 -Encoding utf8
                    aws s3api delete-objects --bucket $bucket --delete "file://$tmp2" | Out-Null
                    Remove-Item $tmp2 -Force
                }
            }
        }

        Invoke-Action "aws s3api delete-bucket --bucket $bucket" { aws s3api delete-bucket --bucket $bucket --region $Region }
    }
} else {
    Write-Host "  (none found)"
}

### 2. Lambda functions ########################################################
Write-Section "Lambda functions"
$functions = (Get-AwsJson "aws lambda list-functions --region $Region").Functions | Where-Object { $_.FunctionName -like "$Prefix*" }
if ($functions) {
    foreach ($f in $functions) {
        $fn = $f.FunctionName
        Invoke-Action "aws lambda delete-function --function-name $fn" { aws lambda delete-function --function-name $fn --region $Region }
        if ($DryRun) {
            Write-Host "  [DRY RUN] aws logs delete-log-group --log-group-name /aws/lambda/$fn" -ForegroundColor Yellow
        } else {
            aws logs delete-log-group --log-group-name "/aws/lambda/$fn" --region $Region 2>$null | Out-Null
        }
    }
} else {
    Write-Host "  (none found)"
}

### 3. API Gateway (HTTP API) ##################################################
Write-Section "API Gateway HTTP APIs"
$apis = (Get-AwsJson "aws apigatewayv2 get-apis --region $Region").Items | Where-Object { $_.Name -like "$Prefix*" }
if ($apis) {
    foreach ($a in $apis) {
        Invoke-Action "aws apigatewayv2 delete-api --api-id $($a.ApiId)" { aws apigatewayv2 delete-api --api-id $a.ApiId --region $Region }
    }
} else {
    Write-Host "  (none found)"
}

### 4. DynamoDB tables ##########################################################
Write-Section "DynamoDB tables"
$tables = (Get-AwsJson "aws dynamodb list-tables --region $Region").TableNames | Where-Object { $_ -like "$Prefix*" }
if ($tables) {
    foreach ($t in $tables) {
        $desc = Get-AwsJson "aws dynamodb describe-table --table-name $t --region $Region"
        if ($desc.Table.DeletionProtectionEnabled -eq $true) {
            Invoke-Action "aws dynamodb update-table --table-name $t --no-deletion-protection-enabled" {
                aws dynamodb update-table --table-name $t --region $Region --no-deletion-protection-enabled
            }
        }
        Invoke-Action "aws dynamodb delete-table --table-name $t" { aws dynamodb delete-table --table-name $t --region $Region }
    }
} else {
    Write-Host "  (none found)"
}

### 5. CloudWatch Log Groups (whatever's left) #################################
Write-Section "CloudWatch Log Groups"
$logGroups = (Get-AwsJson "aws logs describe-log-groups --region $Region").logGroups | Where-Object { $_.logGroupName -like "*$Prefix*" }
if ($logGroups) {
    foreach ($lg in $logGroups) {
        Invoke-Action "aws logs delete-log-group --log-group-name $($lg.logGroupName)" { aws logs delete-log-group --log-group-name $lg.logGroupName --region $Region }
    }
} else {
    Write-Host "  (none found)"
}

### 6. ECR repositories ##########################################################
Write-Section "ECR repositories"
$repos = (Get-AwsJson "aws ecr describe-repositories --region $Region").repositories | Where-Object { $_.repositoryName -like "$Prefix*" }
if ($repos) {
    foreach ($r in $repos) {
        Invoke-Action "aws ecr delete-repository --repository-name $($r.repositoryName) --force" {
            aws ecr delete-repository --repository-name $r.repositoryName --region $Region --force
        }
    }
} else {
    Write-Host "  (none found)"
}

### 7. Cognito User Pools ########################################################
Write-Section "Cognito User Pools"
$pools = (Get-AwsJson "aws cognito-idp list-user-pools --max-results 60 --region $Region").UserPools | Where-Object { $_.Name -like "$Prefix*" }
if ($pools) {
    foreach ($p in $pools) {
        $poolId = $p.Id
        $desc = Get-AwsJson "aws cognito-idp describe-user-pool --user-pool-id $poolId --region $Region"
        $domain = $desc.UserPool.Domain
        if ($domain) {
            Invoke-Action "aws cognito-idp delete-user-pool-domain --domain $domain --user-pool-id $poolId" {
                aws cognito-idp delete-user-pool-domain --domain $domain --user-pool-id $poolId --region $Region
            }
        }
        Invoke-Action "aws cognito-idp delete-user-pool --user-pool-id $poolId" { aws cognito-idp delete-user-pool --user-pool-id $poolId --region $Region }
    }
} else {
    Write-Host "  (none found)"
}

### 8. Step Functions state machines (if the config defines any) ###############
Write-Section "Step Functions state machines"
$stateMachines = (Get-AwsJson "aws stepfunctions list-state-machines --region $Region").stateMachines | Where-Object { $_.name -like "$Prefix*" }
if ($stateMachines) {
    foreach ($sm in $stateMachines) {
        Invoke-Action "aws stepfunctions delete-state-machine --state-machine-arn $($sm.stateMachineArn)" {
            aws stepfunctions delete-state-machine --state-machine-arn $sm.stateMachineArn --region $Region
        }
    }
} else {
    Write-Host "  (none found)"
}

Write-Host ""
if ($DryRun) {
    Write-Host "Dry run complete. Nothing was deleted. Re-run with -Yes to actually delete the resources listed above."
} else {
    Write-Host "Teardown complete."
    Write-Host "Local Terraform state (infra\terraform.tfstate, if you have one on this machine) is now stale -"
    Write-Host "delete it before your next 'terraform init' / 'terraform apply' so Terraform starts from a clean slate."
}
