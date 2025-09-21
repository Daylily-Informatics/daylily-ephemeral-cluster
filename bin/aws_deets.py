#!/usr/bin/env python

import os
import socket

import boto3
import requests
from botocore.exceptions import BotoCoreError, ClientError


def get_aws_deets():
    # Initialize values
    hostname = ""
    ip = ""
    nproc = ""
    instance_type = ""
    region_az = ""
    spot_cost = ""

    # Get hostname
    try:
        hostname = socket.gethostname()
    except Exception:
        hostname = ""

    # Get IP address
    try:
        # Try to get the public IP via AWS metadata service
        # First, obtain the token for IMDSv2
        token_response = requests.put(
            'http://169.254.169.254/latest/api/token',
            headers={'X-aws-ec2-metadata-token-ttl-seconds': '21600'},
            timeout=1
        )
        token = token_response.text

        # Now, get the public IPv4 address
        ip_response = requests.get(
            'http://169.254.169.254/latest/meta-data/public-ipv4',
            headers={'X-aws-ec2-metadata-token': token},
            timeout=1
        )
        if ip_response.status_code == 200:
            ip = ip_response.text
        else:
            # If public IP is not available, get the local IP
            ip_response = requests.get(
                'http://169.254.169.254/latest/meta-data/local-ipv4',
                headers={'X-aws-ec2-metadata-token': token},
                timeout=1
            )
            if ip_response.status_code == 200:
                ip = ip_response.text
            else:
                ip = ""
    except Exception:
        # Fallback to socket method
        try:
            ip = socket.gethostbyname(hostname)
        except Exception:
            ip = ""

    # Get number of processors
    try:
        nproc = os.cpu_count()
    except Exception:
        nproc = ""

    # Get instance type and availability zone
    try:
        # Obtain the token for IMDSv2
        token_response = requests.put(
            'http://169.254.169.254/latest/api/token',
            headers={'X-aws-ec2-metadata-token-ttl-seconds': '21600'},
            timeout=1
        )
        token = token_response.text

        # Get instance type
        instance_type_response = requests.get(
            'http://169.254.169.254/latest/meta-data/instance-type',
            headers={'X-aws-ec2-metadata-token': token},
            timeout=1
        )
        if instance_type_response.status_code == 200:
            instance_type = instance_type_response.text

        # Get availability zone
        az_response = requests.get(
            'http://169.254.169.254/latest/meta-data/placement/availability-zone',
            headers={'X-aws-ec2-metadata-token': token},
            timeout=1
        )
        if az_response.status_code == 200:
            region_az = az_response.text
    except Exception:
        instance_type = ""
        region_az = ""

    # Get spot price
    try:
        # Need to get region from availability zone (e.g., 'us-east-1a' -> 'us-east-1')
        if region_az:
            region = region_az[:-1]
        else:
            # Try to get region from environment variables or default to 'us-east-1'
            region = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')

        # Create a boto3 EC2 client
        ec2_client = boto3.client('ec2', region_name=region)

        # Get spot price history
        response = ec2_client.describe_spot_price_history(
            InstanceTypes=[instance_type],
            AvailabilityZone=region_az,
            ProductDescriptions=['Linux/UNIX'],
            MaxResults=1
        )
        spot_price_history = response.get('SpotPriceHistory', [])
        if spot_price_history:
            spot_cost = spot_price_history[0]['SpotPrice']
        else:
            spot_cost = ""
    except (BotoCoreError, ClientError, Exception):
        spot_cost = ""

    # Return the array of values, converting nproc to string
    return [
        hostname or "",
        ip or "",
        str(nproc) if nproc is not None else "",
        instance_type or "",
        region_az or "",
        spot_cost or ""
    ]


def main():
    print(get_aws_deets())


if __name__ == "__main__":
    main()
