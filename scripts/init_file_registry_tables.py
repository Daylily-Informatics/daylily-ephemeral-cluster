#!/usr/bin/env python3
"""
Initialize DynamoDB tables for the file registry.

Run this from the same environment where your server runs (where boto3 is installed).

Usage:
    python scripts/init_file_registry_tables.py [--region REGION]
"""

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

def main():
    parser = argparse.ArgumentParser(description="Initialize FileRegistry DynamoDB tables")
    parser.add_argument("--region", default="us-west-2", help="AWS region")
    parser.add_argument("--profile", default=None, help="AWS profile")
    args = parser.parse_args()
    
    try:
        from daylib.file_registry import FileRegistry
    except ImportError as e:
        print(f"Error importing FileRegistry: {e}")
        print("Make sure you're running this from an environment with boto3 installed.")
        sys.exit(1)
    
    print(f"Initializing FileRegistry tables in region {args.region}...")
    
    try:
        registry = FileRegistry(region=args.region)
        registry.create_tables_if_not_exist()
        print("\n✅ All tables created/verified successfully!")
        print("\nTables:")
        print(f"  - {registry.files_table_name}")
        print(f"  - {registry.filesets_table_name}")
        print(f"  - {registry.file_workset_usage_table_name}")
    except Exception as e:
        print(f"\n❌ Error creating tables: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

