#!/usr/bin/env python3
"""
Check DynamoDB table existence, stats, and dump sample records.

Usage:
    python scripts/check_dynamodb_table.py <table_name> [-n NUM] [--profile PROFILE] [--region REGION]

Examples:
    python scripts/check_dynamodb_table.py daylily-files -n 5
    python scripts/check_dynamodb_table.py daylily-linked-buckets --profile daylily --region us-west-2
"""

import argparse
import json
import sys
from datetime import datetime
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types from DynamoDB."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj) if obj % 1 else int(obj)
        return super().default(obj)


def check_table(table_name: str, num_records: int = 5, profile: str = None, region: str = "us-west-2"):
    """Check DynamoDB table and dump records."""
    
    # Create session
    session_kwargs = {"region_name": region}
    if profile:
        session_kwargs["profile_name"] = profile
    
    try:
        session = boto3.Session(**session_kwargs)
        dynamodb = session.resource("dynamodb")
        client = session.client("dynamodb")
    except Exception as e:
        print(f"❌ Failed to create AWS session: {e}")
        return False
    
    print(f"\n{'='*60}")
    print(f"DynamoDB Table Check: {table_name}")
    print(f"Region: {region}, Profile: {profile or 'default'}")
    print(f"{'='*60}\n")
    
    # Check if table exists
    try:
        response = client.describe_table(TableName=table_name)
        table_desc = response["Table"]
        print(f"✅ Table EXISTS: {table_name}\n")
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ResourceNotFoundException":
            print(f"❌ Table NOT FOUND: {table_name}")
            print(f"   Create it before using the file registry.")
            return False
        else:
            print(f"❌ Error checking table: {error_code} - {e.response['Error']['Message']}")
            return False
    
    # Print table stats
    print("📊 Table Statistics:")
    print(f"   Status: {table_desc['TableStatus']}")
    print(f"   Item Count: {table_desc.get('ItemCount', 'N/A')}")
    print(f"   Size (bytes): {table_desc.get('TableSizeBytes', 'N/A')}")
    print(f"   Created: {table_desc.get('CreationDateTime', 'N/A')}")
    
    # Key schema
    print(f"\n🔑 Key Schema:")
    for key in table_desc.get("KeySchema", []):
        print(f"   {key['AttributeName']} ({key['KeyType']})")
    
    # GSIs
    gsis = table_desc.get("GlobalSecondaryIndexes", [])
    if gsis:
        print(f"\n📇 Global Secondary Indexes ({len(gsis)}):")
        for gsi in gsis:
            keys = ", ".join(f"{k['AttributeName']}({k['KeyType']})" for k in gsi["KeySchema"])
            print(f"   - {gsi['IndexName']}: {keys}")
    
    # Dump sample records
    if num_records > 0:
        print(f"\n📄 Sample Records (up to {num_records}):")
        print("-" * 60)
        
        try:
            table = dynamodb.Table(table_name)
            response = table.scan(Limit=num_records)
            items = response.get("Items", [])
            
            if not items:
                print("   (no records found)")
            else:
                for i, item in enumerate(items, 1):
                    print(f"\n[Record {i}]")
                    print(json.dumps(item, indent=2, cls=DecimalEncoder, default=str))
                    
            print(f"\n   Total scanned: {response.get('ScannedCount', 0)}")
            
        except ClientError as e:
            print(f"   ❌ Error scanning table: {e}")
    
    return True


def main():
    parser = argparse.ArgumentParser(description="Check DynamoDB table existence and dump records")
    parser.add_argument("table_name", help="DynamoDB table name to check")
    parser.add_argument("-n", "--num-records", type=int, default=5, help="Number of records to dump (default: 5)")
    parser.add_argument("--profile", default=None, help="AWS profile name")
    parser.add_argument("--region", default="us-west-2", help="AWS region (default: us-west-2)")
    
    args = parser.parse_args()
    
    success = check_table(
        table_name=args.table_name,
        num_records=args.num_records,
        profile=args.profile,
        region=args.region,
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

