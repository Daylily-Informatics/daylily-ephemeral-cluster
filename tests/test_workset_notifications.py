"""Tests for workset notification system."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from daylib.workset_notifications import (
    LinearNotificationChannel,
    NotificationEvent,
    NotificationManager,
    SNSNotificationChannel,
)


@pytest.fixture
def sample_event():
    """Create a sample notification event."""
    return NotificationEvent(
        workset_id="test-workset-001",
        event_type="state_change",
        state="in_progress",
        message="Workset processing started",
        priority="normal",
        cluster_name="test-cluster",
    )


@pytest.fixture
def error_event():
    """Create an error notification event."""
    return NotificationEvent(
        workset_id="test-workset-002",
        event_type="error",
        state="error",
        message="Pipeline failed",
        priority="urgent",
        cluster_name="test-cluster",
        error_details="ValueError: Invalid input file format",
    )


def test_sns_notification_success(sample_event):
    """Test successful SNS notification."""
    with patch("daylib.workset_notifications.boto3.Session") as mock_session:
        mock_sns = MagicMock()
        mock_session.return_value.client.return_value = mock_sns
        mock_sns.publish.return_value = {"MessageId": "test-message-id"}
        
        channel = SNSNotificationChannel(
            topic_arn="arn:aws:sns:us-west-2:123456789:test-topic",
            region="us-west-2",
        )
        
        result = channel.send(sample_event)
        
        assert result is True
        mock_sns.publish.assert_called_once()
        
        call_args = mock_sns.publish.call_args
        assert call_args.kwargs["TopicArn"] == "arn:aws:sns:us-west-2:123456789:test-topic"
        assert "test-workset-001" in call_args.kwargs["Message"]
        assert "in_progress" in call_args.kwargs["Message"]


def test_sns_notification_with_error_details(error_event):
    """Test SNS notification with error details."""
    with patch("daylib.workset_notifications.boto3.Session") as mock_session:
        mock_sns = MagicMock()
        mock_session.return_value.client.return_value = mock_sns
        mock_sns.publish.return_value = {"MessageId": "test-message-id"}
        
        channel = SNSNotificationChannel(
            topic_arn="arn:aws:sns:us-west-2:123456789:test-topic",
            region="us-west-2",
        )
        
        result = channel.send(error_event)
        
        assert result is True
        call_args = mock_sns.publish.call_args
        message = call_args.kwargs["Message"]
        
        assert "Error Details:" in message
        assert "ValueError: Invalid input file format" in message


def test_sns_notification_failure(sample_event):
    """Test SNS notification failure handling."""
    from botocore.exceptions import ClientError
    
    with patch("daylib.workset_notifications.boto3.Session") as mock_session:
        mock_sns = MagicMock()
        mock_session.return_value.client.return_value = mock_sns
        mock_sns.publish.side_effect = ClientError(
            {"Error": {"Code": "InvalidParameter"}},
            "Publish",
        )
        
        channel = SNSNotificationChannel(
            topic_arn="arn:aws:sns:us-west-2:123456789:test-topic",
            region="us-west-2",
        )
        
        result = channel.send(sample_event)
        
        assert result is False


def test_linear_notification_error_event(error_event):
    """Test Linear notification for error event."""
    with patch("daylib.workset_notifications.httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "issueCreate": {
                    "success": True,
                    "issue": {
                        "id": "issue-123",
                        "identifier": "DAY-42",
                        "url": "https://linear.app/daylily/issue/DAY-42",
                    },
                }
            }
        }
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client
        
        channel = LinearNotificationChannel(
            api_key="test-api-key",
            team_id="team-123",
        )
        
        result = channel.send(error_event)
        
        assert result is True
        mock_client.post.assert_called_once()
        
        call_args = mock_client.post.call_args
        assert call_args.args[0] == "https://api.linear.app/graphql"
        
        json_data = call_args.kwargs["json"]
        assert "mutation" in json_data["query"].lower()
        assert json_data["variables"]["input"]["teamId"] == "team-123"


def test_linear_notification_skips_state_change(sample_event):
    """Test that Linear skips non-error/completion events."""
    channel = LinearNotificationChannel(
        api_key="test-api-key",
        team_id="team-123",
    )
    
    # Should return True but not create issue
    result = channel.send(sample_event)
    assert result is True


def test_notification_manager_add_channel():
    """Test adding channels to notification manager."""
    manager = NotificationManager()
    
    with patch("daylib.workset_notifications.boto3.Session"):
        channel1 = SNSNotificationChannel(
            topic_arn="arn:aws:sns:us-west-2:123:topic1",
            region="us-west-2",
        )
        channel2 = SNSNotificationChannel(
            topic_arn="arn:aws:sns:us-west-2:123:topic2",
            region="us-west-2",
        )
        
        manager.add_channel(channel1)
        manager.add_channel(channel2)

        assert len(manager.channels) == 2


def test_notification_manager_filters(sample_event, error_event):
    """Test notification filtering."""
    manager = NotificationManager()

    with patch("daylib.workset_notifications.boto3.Session") as mock_session:
        mock_sns = MagicMock()
        mock_session.return_value.client.return_value = mock_sns
        mock_sns.publish.return_value = {"MessageId": "test"}

        channel = SNSNotificationChannel(
            topic_arn="arn:aws:sns:us-west-2:123:topic",
            region="us-west-2",
        )
        manager.add_channel(channel)

        # Filter to only error events
        manager.set_filters(event_types=["error"])

        # Should not send state_change event
        count = manager.notify(sample_event)
        assert count == 0

        # Should send error event
        count = manager.notify(error_event)
        assert count == 1


def test_notification_manager_priority_filter(sample_event, error_event):
    """Test notification filtering by priority."""
    manager = NotificationManager()

    with patch("daylib.workset_notifications.boto3.Session") as mock_session:
        mock_sns = MagicMock()
        mock_session.return_value.client.return_value = mock_sns
        mock_sns.publish.return_value = {"MessageId": "test"}

        channel = SNSNotificationChannel(
            topic_arn="arn:aws:sns:us-west-2:123:topic",
            region="us-west-2",
        )
        manager.add_channel(channel)

        # Filter to only urgent priority
        manager.set_filters(priorities=["urgent"])

        # Should not send normal priority event
        count = manager.notify(sample_event)
        assert count == 0

        # Should send urgent priority event
        count = manager.notify(error_event)
        assert count == 1


def test_notification_manager_multiple_channels(sample_event):
    """Test notification to multiple channels."""
    manager = NotificationManager()

    with patch("daylib.workset_notifications.boto3.Session") as mock_session:
        mock_sns = MagicMock()
        mock_session.return_value.client.return_value = mock_sns
        mock_sns.publish.return_value = {"MessageId": "test"}

        channel1 = SNSNotificationChannel(
            topic_arn="arn:aws:sns:us-west-2:123:topic1",
            region="us-west-2",
        )
        channel2 = SNSNotificationChannel(
            topic_arn="arn:aws:sns:us-west-2:123:topic2",
            region="us-west-2",
        )

        manager.add_channel(channel1)
        manager.add_channel(channel2)

        count = manager.notify(sample_event)

        assert count == 2
        assert mock_sns.publish.call_count == 2

