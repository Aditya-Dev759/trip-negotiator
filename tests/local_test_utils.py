"""
Local testing utilities for mocking AWS services.
"""

import json
import os
from pathlib import Path
from moto import mock_dynamodb, mock_s3
from moto.s3 import responses as s3_responses
import boto3
from datetime import datetime


class LocalAWSEnvironment:
    """Context manager for local AWS mocking."""
    
    def __init__(self):
        self.mock_dynamodb = mock_dynamodb()
        self.mock_s3 = mock_s3()
        self.dynamodb = None
        self.s3 = None
        self.table = None
        
    def __enter__(self):
        self.mock_dynamodb.__enter__()
        self.mock_s3.__enter__()
        
        # Set up DynamoDB
        self.dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        self.table = self.dynamodb.create_table(
            TableName="trip-negotiations-local",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
                {"AttributeName": "userId", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "UserIdIndex",
                    "KeySchema": [
                        {"AttributeName": "userId", "KeyType": "HASH"},
                        {"AttributeName": "timestamp", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {
                        "ReadCapacityUnits": 5,
                        "WriteCapacityUnits": 5,
                    },
                }
            ],
            BillingMode="PROVISIONED",
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        )
        
        # Set up S3
        self.s3 = boto3.client("s3", region_name="us-east-1")
        self.s3.create_bucket(Bucket="trip-negotiator-data-local")
        
        # Upload reference data
        self._upload_reference_data()
        
        # Set env vars for local testing
        os.environ["DYNAMODB_TABLE"] = "trip-negotiations-local"
        os.environ["S3_BUCKET"] = "trip-negotiator-data-local"
        os.environ["REGION"] = "us-east-1"
        os.environ["ENVIRONMENT"] = "local"
        
        return self
    
    def __exit__(self, *args):
        self.mock_dynamodb.__exit__(*args)
        self.mock_s3.__exit__(*args)
    
    def _upload_reference_data(self):
        """Upload reference data files to mocked S3."""
        project_root = Path(__file__).parent.parent
        data_dir = project_root / "data"
        
        for filename in ["destinations.json", "cost_baselines.json", "visa_rules.json", "seasonal_notes.json"]:
            filepath = data_dir / filename
            with open(filepath, "r") as f:
                content = f.read()
            self.s3.put_object(
                Bucket="trip-negotiator-data-local",
                Key=filename,
                Body=content,
            )


def load_reference_data(filename):
    """Load reference data from local files."""
    # Data files are in the project root 'data/' directory
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data"
    filepath = data_dir / filename
    with open(filepath, "r") as f:
        return json.load(f)


def print_step(step_num, message, data=None):
    """Pretty-print test steps."""
    print(f"\n{'='*70}")
    print(f"STEP {step_num}: {message}")
    print(f"{'='*70}")
    if data:
        print(json.dumps(data, indent=2))
