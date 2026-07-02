"""
Local DynamoDB setup for testing.
Run this once to set up the local DynamoDB environment.
"""

import boto3
from moto import mock_dynamodb
import json

# Create table in mocked DynamoDB
@mock_dynamodb
def create_local_table():
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    
    table = dynamodb.create_table(
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
    
    print(f"✅ Created local DynamoDB table: {table.table_name}")
    return table


if __name__ == "__main__":
    create_local_table()
    print("Local DynamoDB setup complete!")
