#!/usr/bin/env python3
"""
Initialize DynamoDB tables for the biospecimen registry.

This creates four tables:
  - daylily-subjects: Subject/patient records
  - daylily-biospecimens: Biospecimen/collection batch records
  - daylily-biosamples: Biosample/specimen records
  - daylily-libraries: Sequencing library records

Run this from the same environment where your server runs (where boto3 is installed).

Usage:
    python scripts/init_biospecimen_tables.py [--region REGION] [--profile PROFILE]
"""

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def main():
    parser = argparse.ArgumentParser(description="Initialize Biospecimen DynamoDB tables")
    parser.add_argument("--region", default="us-west-2", help="AWS region")
    parser.add_argument("--profile", default=None, help="AWS profile")
    args = parser.parse_args()
    
    try:
        from daylib.biospecimen import BiospecimenRegistry
    except ImportError as e:
        print(f"Error importing BiospecimenRegistry: {e}")
        print("Make sure you're running this from an environment with boto3 installed.")
        sys.exit(1)
    
    print(f"Initializing Biospecimen tables in region {args.region}...")
    if args.profile:
        print(f"Using AWS profile: {args.profile}")
    
    try:
        registry = BiospecimenRegistry(
            subjects_table_name="daylily-subjects",
            biosamples_table_name="daylily-biosamples",
            libraries_table_name="daylily-libraries",
            region=args.region,
            profile=args.profile,
        )
        registry.create_tables_if_not_exist()
        print("\n✅ All biospecimen tables created/verified successfully!")
        print("\nTables:")
        print(f"  - {registry.subjects_table_name}")
        print(f"  - {registry.biospecimens_table_name}")
        print(f"  - {registry.biosamples_table_name}")
        print(f"  - {registry.libraries_table_name}")
    except Exception as e:
        print(f"\n❌ Error creating biospecimen tables: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

