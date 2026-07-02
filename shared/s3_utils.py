import os
import json
import boto3

from pathlib import Path

_s3 = None


def _get_client():
    """Lazily create the boto3 S3 client (see dynamo_utils._get_resource for why)."""
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return _s3


def get_bucket():
    """Get S3 bucket name from environment."""
    return os.environ.get("S3_BUCKET", "tripnegotiator-data")


def load_local_fallback(filename: str) -> dict:
    """Load JSON file from local data/ directory if possible."""
    curr = Path(__file__).resolve()
    for parent in curr.parents:
        data_dir = parent / "data"
        if data_dir.is_dir():
            file_path = data_dir / filename
            if file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    print(f"Error reading local file {filename}: {e}")
    raise FileNotFoundError(f"Could not locate local fallback file: {filename}")


def load_destinations() -> dict:
    """Load destinations reference data from S3, falling back to local file."""
    try:
        bucket = get_bucket()
        obj = _get_client().get_object(Bucket=bucket, Key="destinations.json")
        return json.loads(obj["Body"].read())
    except Exception as e:
        print(f"S3 load_destinations failed, falling back to local...")
        return load_local_fallback("destinations.json")


def load_cost_baselines() -> dict:
    """Load cost baselines reference data from S3, falling back to local file."""
    try:
        bucket = get_bucket()
        obj = _get_client().get_object(Bucket=bucket, Key="cost_baselines.json")
        return json.loads(obj["Body"].read())
    except Exception as e:
        print(f"S3 load_cost_baselines failed, falling back to local...")
        return load_local_fallback("cost_baselines.json")


def load_visa_rules() -> dict:
    """Load visa requirements reference data from S3, falling back to local file."""
    try:
        bucket = get_bucket()
        obj = _get_client().get_object(Bucket=bucket, Key="visa_rules.json")
        return json.loads(obj["Body"].read())
    except Exception as e:
        print(f"S3 load_visa_rules failed, falling back to local...")
        return load_local_fallback("visa_rules.json")


def load_seasonal_notes() -> dict:
    """Load seasonal notes reference data from S3, falling back to local file."""
    try:
        bucket = get_bucket()
        obj = _get_client().get_object(Bucket=bucket, Key="seasonal_notes.json")
        return json.loads(obj["Body"].read())
    except Exception as e:
        print(f"S3 load_seasonal_notes failed, falling back to local...")
        return load_local_fallback("seasonal_notes.json")


def load_country_currencies() -> dict:
    """Load ISO country-code -> currency-code reference data from S3, falling
    back to local file. Unlike the other static files here, this rarely if
    ever needs updating (currency-per-country is stable data), but it still
    follows the S3-with-local-fallback pattern for consistency.
    """
    try:
        bucket = get_bucket()
        obj = _get_client().get_object(Bucket=bucket, Key="country_currencies.json")
        return json.loads(obj["Body"].read())
    except Exception as e:
        print(f"S3 load_country_currencies failed, falling back to local...")
        return load_local_fallback("country_currencies.json")
