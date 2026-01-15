"""Notification system for workset monitoring events.

Supports SNS, email, and Linear API integration for alerting.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import boto3
import httpx
from botocore.exceptions import ClientError

LOGGER = logging.getLogger("daylily.workset_notifications")


@dataclass
class NotificationEvent:
    """Workset event to be notified."""
    workset_id: str
    event_type: str  # state_change, error, completion, timeout
    state: str
    message: str
    details: Optional[Dict[str, Any]] = None
    priority: str = "normal"
    cluster_name: Optional[str] = None
    error_details: Optional[str] = None


class NotificationChannel(ABC):
    """Abstract base class for notification channels."""
    
    @abstractmethod
    def send(self, event: NotificationEvent) -> bool:
        """Send notification for an event.
        
        Args:
            event: Event to notify about
            
        Returns:
            True if sent successfully, False otherwise
        """
        pass


class SNSNotificationChannel(NotificationChannel):
    """Send notifications via AWS SNS."""
    
    def __init__(
        self,
        topic_arn: str,
        region: str,
        profile: Optional[str] = None,
    ):
        """Initialize SNS notification channel.
        
        Args:
            topic_arn: SNS topic ARN
            region: AWS region
            profile: AWS profile name (optional)
        """
        session_kwargs = {"region_name": region}
        if profile:
            session_kwargs["profile_name"] = profile
        
        session = boto3.Session(**session_kwargs)
        self.sns = session.client("sns")
        self.topic_arn = topic_arn
    
    def send(self, event: NotificationEvent) -> bool:
        """Send SNS notification."""
        subject = f"Daylily Workset {event.event_type.replace('_', ' ').title()}: {event.workset_id}"
        
        message_lines = [
            f"Workset: {event.workset_id}",
            f"Event: {event.event_type}",
            f"State: {event.state}",
            f"Priority: {event.priority}",
            "",
            event.message,
        ]
        
        if event.cluster_name:
            message_lines.insert(4, f"Cluster: {event.cluster_name}")
        
        if event.error_details:
            message_lines.extend([
                "",
                "Error Details:",
                event.error_details,
            ])
        
        if event.details:
            message_lines.extend([
                "",
                "Additional Details:",
                json.dumps(event.details, indent=2),
            ])
        
        message = "\n".join(message_lines)
        
        try:
            self.sns.publish(
                TopicArn=self.topic_arn,
                Subject=subject[:100],  # SNS subject limit
                Message=message,
                MessageAttributes={
                    "workset_id": {"DataType": "String", "StringValue": event.workset_id},
                    "event_type": {"DataType": "String", "StringValue": event.event_type},
                    "state": {"DataType": "String", "StringValue": event.state},
                    "priority": {"DataType": "String", "StringValue": event.priority},
                },
            )
            LOGGER.info("Sent SNS notification for workset %s", event.workset_id)
            return True
        except ClientError as e:
            LOGGER.error("Failed to send SNS notification: %s", str(e))
            return False


class LinearNotificationChannel(NotificationChannel):
    """Send notifications to Linear project management tool."""
    
    def __init__(
        self,
        api_key: str,
        team_id: str,
        project_id: Optional[str] = None,
    ):
        """Initialize Linear notification channel.
        
        Args:
            api_key: Linear API key
            team_id: Linear team ID
            project_id: Optional project ID to associate issues with
        """
        self.api_key = api_key
        self.team_id = team_id
        self.project_id = project_id
        self.api_url = "https://api.linear.app/graphql"

    def send(self, event: NotificationEvent) -> bool:
        """Create Linear issue for workset event."""
        # Only create issues for errors and completions
        if event.event_type not in ["error", "completion"]:
            return True

        title = f"[Daylily] {event.workset_id} - {event.state}"

        description_parts = [
            f"**Workset:** {event.workset_id}",
            f"**Event:** {event.event_type}",
            f"**State:** {event.state}",
            f"**Priority:** {event.priority}",
            "",
            event.message,
        ]

        if event.cluster_name:
            description_parts.insert(4, f"**Cluster:** {event.cluster_name}")

        if event.error_details:
            description_parts.extend([
                "",
                "## Error Details",
                f"```\n{event.error_details}\n```",
            ])

        description = "\n".join(description_parts)

        # Determine priority (1=urgent, 2=high, 3=normal, 4=low)
        linear_priority = 3
        if event.priority == "urgent":
            linear_priority = 1
        elif event.event_type == "error":
            linear_priority = 2

        mutation = """
        mutation CreateIssue($input: IssueCreateInput!) {
            issueCreate(input: $input) {
                success
                issue {
                    id
                    identifier
                    url
                }
            }
        }
        """

        variables = {
            "input": {
                "teamId": self.team_id,
                "title": title,
                "description": description,
                "priority": linear_priority,
            }
        }

        if self.project_id:
            variables["input"]["projectId"] = self.project_id

        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client() as client:
                response = client.post(
                    self.api_url,
                    json={"query": mutation, "variables": variables},
                    headers=headers,
                    timeout=10.0,
                )
                response.raise_for_status()

                data = response.json()
                if data.get("data", {}).get("issueCreate", {}).get("success"):
                    issue = data["data"]["issueCreate"]["issue"]
                    LOGGER.info(
                        "Created Linear issue %s for workset %s: %s",
                        issue["identifier"],
                        event.workset_id,
                        issue["url"],
                    )
                    return True
                else:
                    LOGGER.error("Linear API returned failure: %s", data)
                    return False
        except Exception as e:
            LOGGER.error("Failed to create Linear issue: %s", str(e))
            return False


class NotificationManager:
    """Manage multiple notification channels with filtering rules."""

    def __init__(self):
        """Initialize notification manager."""
        self.channels: List[NotificationChannel] = []
        self.filters: Dict[str, List[str]] = {
            "event_types": [],  # Empty = all events
            "states": [],  # Empty = all states
            "priorities": [],  # Empty = all priorities
        }

    def add_channel(self, channel: NotificationChannel) -> None:
        """Add a notification channel.

        Args:
            channel: Notification channel to add
        """
        self.channels.append(channel)
        LOGGER.info("Added notification channel: %s", channel.__class__.__name__)

    def set_filters(
        self,
        event_types: Optional[List[str]] = None,
        states: Optional[List[str]] = None,
        priorities: Optional[List[str]] = None,
    ) -> None:
        """Set notification filters.

        Args:
            event_types: List of event types to notify on (None = all)
            states: List of states to notify on (None = all)
            priorities: List of priorities to notify on (None = all)
        """
        if event_types is not None:
            self.filters["event_types"] = event_types
        if states is not None:
            self.filters["states"] = states
        if priorities is not None:
            self.filters["priorities"] = priorities

    def notify(self, event: NotificationEvent) -> int:
        """Send notification to all channels if filters match.

        Args:
            event: Event to notify about

        Returns:
            Number of channels that successfully sent notification
        """
        # Apply filters
        if self.filters["event_types"] and event.event_type not in self.filters["event_types"]:
            return 0
        if self.filters["states"] and event.state not in self.filters["states"]:
            return 0
        if self.filters["priorities"] and event.priority not in self.filters["priorities"]:
            return 0

        success_count = 0
        for channel in self.channels:
            try:
                if channel.send(event):
                    success_count += 1
            except Exception as e:
                LOGGER.error(
                    "Notification channel %s failed: %s",
                    channel.__class__.__name__,
                    e,
                )

        return success_count

