"""
File Upload Module for Daylily

Provides S3 presigned URL generation for direct uploads to customer buckets,
multipart upload support, and checksum validation.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def _utc_now_iso() -> str:
    """Return current UTC time in ISO format with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

import boto3
from botocore.exceptions import ClientError

LOGGER = logging.getLogger("daylily.file_upload")


@dataclass
class UploadSession:
    """Represents an upload session for tracking multipart uploads."""
    session_id: str
    customer_id: str
    bucket_name: str
    object_key: str
    file_name: str
    file_size_bytes: int
    content_type: str = "application/octet-stream"
    
    # Multipart upload tracking
    upload_id: Optional[str] = None
    parts: List[Dict[str, Any]] = field(default_factory=list)
    
    # Status
    status: str = "pending"  # pending, uploading, completed, failed, cancelled
    
    # Checksums
    expected_md5: Optional[str] = None
    actual_md5: Optional[str] = None

    # Timestamps
    created_at: str = field(default_factory=_utc_now_iso)
    completed_at: Optional[str] = None


@dataclass
class PresignedUrlResponse:
    """Response containing presigned URL for upload."""
    url: str
    fields: Dict[str, str]  # For POST uploads
    expires_in: int
    method: str = "PUT"  # PUT for direct upload, POST for form upload


class FileUploadManager:
    """Manage file uploads to S3 with presigned URLs and multipart support."""
    
    def __init__(
        self,
        region: str = "us-west-2",
        profile: Optional[str] = None,
        default_expiration: int = 3600,  # 1 hour
    ):
        """Initialize file upload manager.
        
        Args:
            region: AWS region
            profile: AWS profile name
            default_expiration: Default presigned URL expiration in seconds
        """
        session_kwargs = {"region_name": region}
        if profile:
            session_kwargs["profile_name"] = profile
        
        session = boto3.Session(**session_kwargs)
        self.s3 = session.client("s3")
        self.region = region
        self.default_expiration = default_expiration
    
    def generate_presigned_put_url(
        self,
        bucket_name: str,
        object_key: str,
        content_type: str = "application/octet-stream",
        expiration: Optional[int] = None,
        expected_md5: Optional[str] = None,
    ) -> PresignedUrlResponse:
        """Generate a presigned PUT URL for direct upload.
        
        Args:
            bucket_name: Target S3 bucket
            object_key: Object key (path) in the bucket
            content_type: MIME type of the file
            expiration: URL expiration in seconds
            expected_md5: Expected MD5 checksum (base64 encoded)
            
        Returns:
            PresignedUrlResponse with the upload URL
        """
        expiration = expiration or self.default_expiration
        
        params = {
            "Bucket": bucket_name,
            "Key": object_key,
            "ContentType": content_type,
        }
        
        if expected_md5:
            params["ContentMD5"] = expected_md5
        
        try:
            url = self.s3.generate_presigned_url(
                "put_object",
                Params=params,
                ExpiresIn=expiration,
            )
            
            return PresignedUrlResponse(
                url=url,
                fields={},
                expires_in=expiration,
                method="PUT",
            )
        except ClientError as e:
            LOGGER.error("Failed to generate presigned PUT URL: %s", str(e))
            raise
    
    def generate_presigned_post(
        self,
        bucket_name: str,
        object_key: str,
        content_type: str = "application/octet-stream",
        max_size_bytes: int = 5 * 1024 * 1024 * 1024,  # 5GB
        expiration: Optional[int] = None,
    ) -> PresignedUrlResponse:
        """Generate a presigned POST URL for form-based upload.
        
        Args:
            bucket_name: Target S3 bucket
            object_key: Object key (path) in the bucket
            content_type: MIME type of the file
            max_size_bytes: Maximum allowed file size
            expiration: URL expiration in seconds
            
        Returns:
            PresignedUrlResponse with the upload URL and form fields
        """
        expiration = expiration or self.default_expiration
        
        conditions = [
            {"bucket": bucket_name},
            ["starts-with", "$key", object_key.rsplit("/", 1)[0] + "/" if "/" in object_key else ""],
            ["content-length-range", 1, max_size_bytes],
            {"Content-Type": content_type},
        ]

        fields = {
            "Content-Type": content_type,
        }

        try:
            response = self.s3.generate_presigned_post(
                Bucket=bucket_name,
                Key=object_key,
                Fields=fields,
                Conditions=conditions,
                ExpiresIn=expiration,
            )

            return PresignedUrlResponse(
                url=response["url"],
                fields=response["fields"],
                expires_in=expiration,
                method="POST",
            )
        except ClientError as e:
            LOGGER.error("Failed to generate presigned POST URL: %s", str(e))
            raise

    def initiate_multipart_upload(
        self,
        bucket_name: str,
        object_key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Initiate a multipart upload.

        Args:
            bucket_name: Target S3 bucket
            object_key: Object key (path) in the bucket
            content_type: MIME type of the file

        Returns:
            Upload ID for the multipart upload
        """
        try:
            response = self.s3.create_multipart_upload(
                Bucket=bucket_name,
                Key=object_key,
                ContentType=content_type,
            )
            upload_id: str = str(response["UploadId"])
            LOGGER.info("Initiated multipart upload %s for %s/%s", upload_id, bucket_name, object_key)
            return upload_id
        except ClientError as e:
            LOGGER.error("Failed to initiate multipart upload: %s", str(e))
            raise

    def generate_part_upload_url(
        self,
        bucket_name: str,
        object_key: str,
        upload_id: str,
        part_number: int,
        expiration: Optional[int] = None,
    ) -> str:
        """Generate a presigned URL for uploading a part.

        Args:
            bucket_name: Target S3 bucket
            object_key: Object key (path) in the bucket
            upload_id: Multipart upload ID
            part_number: Part number (1-10000)
            expiration: URL expiration in seconds

        Returns:
            Presigned URL for uploading the part
        """
        expiration = expiration or self.default_expiration

        try:
            url: str = str(self.s3.generate_presigned_url(
                "upload_part",
                Params={
                    "Bucket": bucket_name,
                    "Key": object_key,
                    "UploadId": upload_id,
                    "PartNumber": part_number,
                },
                ExpiresIn=expiration,
            ))
            return url
        except ClientError as e:
            LOGGER.error("Failed to generate part upload URL: %s", str(e))
            raise

    def complete_multipart_upload(
        self,
        bucket_name: str,
        object_key: str,
        upload_id: str,
        parts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Complete a multipart upload.

        Args:
            bucket_name: Target S3 bucket
            object_key: Object key (path) in the bucket
            upload_id: Multipart upload ID
            parts: List of parts with PartNumber and ETag

        Returns:
            Response from S3 with location and ETag
        """
        try:
            response = self.s3.complete_multipart_upload(
                Bucket=bucket_name,
                Key=object_key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
            LOGGER.info("Completed multipart upload %s for %s/%s", upload_id, bucket_name, object_key)
            return {
                "location": response.get("Location"),
                "bucket": response.get("Bucket"),
                "key": response.get("Key"),
                "etag": response.get("ETag"),
            }
        except ClientError as e:
            LOGGER.error("Failed to complete multipart upload: %s", str(e))
            raise

    def abort_multipart_upload(
        self,
        bucket_name: str,
        object_key: str,
        upload_id: str,
    ) -> bool:
        """Abort a multipart upload.

        Args:
            bucket_name: Target S3 bucket
            object_key: Object key (path) in the bucket
            upload_id: Multipart upload ID

        Returns:
            True if aborted successfully
        """
        try:
            self.s3.abort_multipart_upload(
                Bucket=bucket_name,
                Key=object_key,
                UploadId=upload_id,
            )
            LOGGER.info("Aborted multipart upload %s for %s/%s", upload_id, bucket_name, object_key)
            return True
        except ClientError as e:
            LOGGER.error("Failed to abort multipart upload: %s", str(e))
            return False

    def verify_upload(
        self,
        bucket_name: str,
        object_key: str,
        expected_size: Optional[int] = None,
        expected_etag: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Verify an uploaded file.

        Args:
            bucket_name: S3 bucket
            object_key: Object key
            expected_size: Expected file size in bytes
            expected_etag: Expected ETag (MD5 for single-part uploads)

        Returns:
            Tuple of (is_valid, file_info)
        """
        try:
            response = self.s3.head_object(Bucket=bucket_name, Key=object_key)

            file_info = {
                "size": response["ContentLength"],
                "etag": response["ETag"].strip('"'),
                "content_type": response.get("ContentType"),
                "last_modified": response["LastModified"].isoformat(),
            }

            is_valid = True

            if expected_size is not None and file_info["size"] != expected_size:
                LOGGER.warning(
                    "Size mismatch for %s/%s: expected %d, got %d",
                    bucket_name, object_key, expected_size, file_info["size"]
                )
                is_valid = False

            if expected_etag is not None and file_info["etag"] != expected_etag:
                LOGGER.warning(
                    "ETag mismatch for %s/%s: expected %s, got %s",
                    bucket_name, object_key, expected_etag, file_info["etag"]
                )
                is_valid = False

            return is_valid, file_info

        except ClientError as e:
            LOGGER.error("Failed to verify upload %s/%s: %s", bucket_name, object_key, str(e))
            return False, {"error": str(e)}


def generate_upload_path(
    customer_id: str,
    filename: str,
    prefix: str = "uploads",
    include_timestamp: bool = True,
) -> str:
    """Generate a standardized upload path for a customer.

    Args:
        customer_id: Customer ID
        filename: Original filename
        prefix: Path prefix (default: uploads)
        include_timestamp: Whether to include timestamp in path

    Returns:
        S3 object key path
    """
    if include_timestamp:
        timestamp = datetime.now(timezone.utc).strftime("%Y/%m/%d")
        return f"{prefix}/{customer_id}/{timestamp}/{filename}"
    return f"{prefix}/{customer_id}/{filename}"

