#!/usr/bin/env python3
"""
Orlando PD Active Calls Monitor
Monitors Orlando Police Department active calls for specific locations and sends notifications.
"""

import argparse
import sys
import time
import logging
import requests
import re
import xml.etree.ElementTree as ET
import resend
from typing import Optional, List, Dict
from dataclasses import dataclass
from datetime import datetime

# Configuration defaults
DEFAULT_POLL_INTERVAL = 30  # seconds
DEFAULT_SEARCH_TERM = "FORELAND"
ORLANDO_PD_URL = "https://www1.cityoforlando.net/opd/activecalls/activecadpolice.xml"

class NotificationTracker:
    """Tracks which incidents have already been notified to prevent duplicates."""
    
    def __init__(self):
        """Initialize the notification tracker with empty sets."""
        self.notified_incidents = set()  # Set of incident numbers already notified
        self.logger = logging.getLogger(__name__)
    
    def is_already_notified(self, incident_number: str) -> bool:
        """
        Check if an incident has already been notified.
        
        Args:
            incident_number: Incident number to check
            
        Returns:
            True if already notified, False otherwise
        """
        return incident_number in self.notified_incidents
    
    def mark_as_notified(self, incident_number: str) -> None:
        """
        Mark an incident as notified.
        
        Args:
            incident_number: Incident number to mark as notified
        """
        self.notified_incidents.add(incident_number)
        self.logger.debug(f"Marked incident {incident_number} as notified")
    
    def get_notification_count(self) -> int:
        """
        Get the total number of incidents that have been notified.
        
        Returns:
            Number of notified incidents
        """
        return len(self.notified_incidents)

@dataclass
class PoliceCall:
    """Data structure for a police call record."""
    incident_number: str
    datetime_str: str
    call_type: str
    location: str
    district: str
    parsed_datetime: Optional[datetime] = None

    def __post_init__(self):
        """Parse the datetime string after initialization."""
        try:
            # Parse datetime format like "5/27/2025 13:16"
            self.parsed_datetime = datetime.strptime(self.datetime_str, "%m/%d/%Y %H:%M")
        except ValueError:
            # If parsing fails, leave as None
            pass

class Config:
    """Configuration class to hold all script settings."""
    
    def __init__(self, ntfy_topic: str, search_term: str = DEFAULT_SEARCH_TERM, 
                 poll_interval: int = DEFAULT_POLL_INTERVAL, 
                 resend_api_key: Optional[str] = None, email_to: Optional[str] = None,
                 email_from: Optional[str] = None):
        """
        Initialize configuration.
        
        Args:
            ntfy_topic: The ntfy.sh topic to send notifications to
            search_term: The term to search for in call locations
            poll_interval: How often to check for new calls (seconds)
            resend_api_key: Resend API key for email notifications
            email_to: Email address to send notifications to
            email_from: Email address to send notifications from
        """
        self.ntfy_topic = ntfy_topic
        self.search_term = search_term.upper()  # Case insensitive search
        self.poll_interval = poll_interval
        self.ntfy_url = f"https://ntfy.sh/{ntfy_topic}"
        
        # Email configuration
        self.resend_api_key = resend_api_key
        self.email_from = email_from
        
        # Parse multiple email addresses (comma-separated)
        if email_to:
            self.email_to = [email.strip() for email in email_to.split(',') if email.strip()]
        else:
            self.email_to = []
            
        self.email_enabled = all([resend_api_key, self.email_to, email_from])

def parse_arguments() -> Config:
    """
    Parse command line arguments and return configuration.
    
    Returns:
        Config object with parsed settings
    """
    parser = argparse.ArgumentParser(
        description="Monitor Orlando PD active calls for specific locations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --topic my-alerts
  %(prog)s --topic police-watch --search FORELAND --interval 60
        """
    )
    
    parser.add_argument(
        "--topic", 
        required=True,
        help="ntfy.sh topic name to send notifications to"
    )
    
    parser.add_argument(
        "--search",
        default=DEFAULT_SEARCH_TERM,
        help=f"Search term for call locations (default: {DEFAULT_SEARCH_TERM})"
    )
    
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_POLL_INTERVAL,
        help=f"Polling interval in seconds (default: {DEFAULT_POLL_INTERVAL})"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--resend-api-key",
        help="Resend API key for email notifications"
    )
    
    parser.add_argument(
        "--email-to",
        help="Email address(es) to send notifications to (comma-separated for multiple)"
    )
    
    parser.add_argument(
        "--email-from",
        help="Email address to send notifications from"
    )
    
    args = parser.parse_args()
    
    return Config(
        ntfy_topic=args.topic,
        search_term=args.search,
        poll_interval=args.interval,
        resend_api_key=args.resend_api_key,
        email_to=args.email_to,
        email_from=args.email_from
    )

def setup_logging(verbose: bool = False) -> None:
    """
    Setup logging configuration.
    
    Args:
        verbose: Enable debug level logging if True
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def fetch_active_calls() -> str:
    """
    Fetch active calls data from Orlando PD XML endpoint.
    
    Returns:
        Raw XML/text content from Orlando PD
    
    Raises:
        requests.RequestException: If the HTTP request fails
    """
    logger = logging.getLogger(__name__)
    
    try:
        logger.debug(f"Fetching data from {ORLANDO_PD_URL}")
        
        # Set timeout and headers for the request
        headers = {
            'User-Agent': 'Orlando-PD-Monitor/1.0'
        }
        
        response = requests.get(ORLANDO_PD_URL, headers=headers, timeout=30)
        response.raise_for_status()  # Raise exception for bad status codes
        
        logger.debug(f"Successfully fetched {len(response.text)} characters of data")
        return response.text
        
    except requests.exceptions.Timeout:
        logger.error("Timeout while fetching Orlando PD data")
        raise
    except requests.exceptions.ConnectionError:
        logger.error("Connection error while fetching Orlando PD data")
        raise
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error while fetching Orlando PD data: {e}")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error while fetching Orlando PD data: {e}")
        raise

def parse_active_calls(raw_data: str) -> List[PoliceCall]:
    """
    Parse the XML data from Orlando PD into structured call records.
    
    The data format is XML with structure:
    <CALLS>
        <CALL incident="2025-00192513">
            <DATE>5/27/2025 13:36</DATE>
            <DESC>General investigation</DESC>
            <LOCATION>2400 BLOCK 29TH ST</LOCATION>
            <DISTRICT>G8</DISTRICT>
        </CALL>
        ...
    </CALLS>
    
    Args:
        raw_data: Raw XML content from Orlando PD endpoint
        
    Returns:
        List of PoliceCall objects
    """
    logger = logging.getLogger(__name__)
    calls = []
    
    if not raw_data.strip():
        logger.warning("No data received from Orlando PD")
        return calls
    
    try:
        # Remove BOM if present and clean up the XML data
        clean_data = raw_data
        if clean_data.startswith('\ufeff'):  # UTF-8 BOM
            clean_data = clean_data[1:]
        # Also try to remove the visible BOM characters that sometimes appear
        if clean_data.startswith('ï»¿'):
            clean_data = clean_data[3:]
        
        # Parse the XML data
        root = ET.fromstring(clean_data)
        
        # Find all CALL elements
        call_elements = root.findall('CALL')
        
        for call_element in call_elements:
            # Extract data from XML elements
            incident_number = call_element.get('incident', '')
            date_elem = call_element.find('DATE')
            desc_elem = call_element.find('DESC') 
            location_elem = call_element.find('LOCATION')
            district_elem = call_element.find('DISTRICT')
            
            # Skip if any required elements are missing
            if not all([date_elem is not None, desc_elem is not None, 
                       location_elem is not None, district_elem is not None]):
                logger.debug(f"Skipping incomplete call record: {incident_number}")
                continue
            
            # Extract text content
            datetime_str = date_elem.text.strip() if date_elem.text else ''
            call_type = desc_elem.text.strip() if desc_elem.text else ''
            location = location_elem.text.strip() if location_elem.text else ''
            district = district_elem.text.strip() if district_elem.text else ''
            
            # Create PoliceCall object
            call = PoliceCall(
                incident_number=incident_number,
                datetime_str=datetime_str,
                call_type=call_type,
                location=location,
                district=district
            )
            
            calls.append(call)
            logger.debug(f"Parsed call: {incident_number} | {datetime_str} | {call_type} | {location} | {district}")
        
        logger.info(f"Successfully parsed {len(calls)} active calls")
        
    except ET.ParseError as e:
        logger.error(f"XML parsing error: {e}")
        logger.debug(f"Raw data sample: {raw_data[:500]}...")
    except Exception as e:
        logger.error(f"Error parsing active calls data: {e}")
        logger.debug(f"Raw data sample: {raw_data[:500]}...")
    
    return calls

def search_calls_by_location(calls: List[PoliceCall], search_term: str) -> List[PoliceCall]:
    """
    Search police calls for a specific location term.
    
    Args:
        calls: List of PoliceCall objects to search
        search_term: Term to search for in call locations (case-insensitive)
        
    Returns:
        List of PoliceCall objects that match the search term
    """
    logger = logging.getLogger(__name__)
    matches = []
    
    if not calls:
        logger.debug("No calls to search")
        return matches
    
    # Convert search term to uppercase for case-insensitive comparison
    search_upper = search_term.upper()
    
    for call in calls:
        # Check if search term is in the location (case-insensitive)
        if search_upper in call.location.upper():
            matches.append(call)
            logger.debug(f"MATCH FOUND: {call.incident_number} | {call.location}")
    
    logger.info(f"Found {len(matches)} calls matching '{search_term}' in location")
    return matches

def send_notification(call: PoliceCall, config: Config, tracker: NotificationTracker) -> bool:
    """
    Send a notification via ntfy.sh for a matching police call.
    
    Args:
        call: PoliceCall object containing incident details
        config: Configuration object with ntfy settings
        tracker: NotificationTracker to prevent duplicate notifications
        
    Returns:
        True if notification was sent successfully, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    # Check if this incident has already been notified
    if tracker.is_already_notified(call.incident_number):
        logger.info(f"⏭️  Skipping duplicate notification for incident {call.incident_number}")
        return False
    
    try:
        # Format the notification message
        message = format_notification_message(call, config.search_term)
        
        # Set up headers for the notification
        headers = {
            "Title": f"Orlando PD Alert: {config.search_term}",
            "Priority": "urgent", 
            "Tags": "police,alert,orlando"
        }
        
        logger.debug(f"Sending notification to {config.ntfy_url}")
        logger.debug(f"Message: {message}")
        
        # Send the notification
        response = requests.post(
            config.ntfy_url,
            data=message,
            headers=headers,
            timeout=10
        )
        
        response.raise_for_status()
        
        # Mark this incident as notified
        tracker.mark_as_notified(call.incident_number)
        
        logger.info(f"✅ Notification sent successfully for incident {call.incident_number}")
        return True
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout sending notification for incident {call.incident_number}")
        return False
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error sending notification for incident {call.incident_number}")
        return False
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error sending notification for incident {call.incident_number}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending notification for incident {call.incident_number}: {e}")
        return False

def format_notification_message(call: PoliceCall, search_term: str) -> str:
    """
    Format a police call into a notification message.
    
    Args:
        call: PoliceCall object to format
        search_term: The search term that triggered this notification
        
    Returns:
        Formatted notification message string
    """
    message = f"""ORLANDO PD ALERT: {search_term}

Type: {call.call_type}
Time: {call.datetime_str}
Location: {call.location}
District: {call.district}
Incident: {call.incident_number}

This call contains "{search_term}" in the location field."""
    
    return message

def send_email_notification(call: PoliceCall, config: Config) -> bool:
    """
    Send an email notification via Resend for a matching police call.
    
    Args:
        call: PoliceCall object containing incident details
        config: Configuration object with email settings
        
    Returns:
        True if email was sent successfully, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    if not config.email_enabled:
        logger.debug("Email notifications not configured, skipping email")
        return False
    
    try:
        # Set up Resend API key
        resend.api_key = config.resend_api_key
        
        # Format email content
        subject = f"Orlando PD Alert: {config.search_term} - {call.call_type}"
        
        html_content = f"""
        <html>
        <body>
            <h2>🚨 Orlando PD Alert: {config.search_term}</h2>
            
            <table style="border-collapse: collapse; width: 100%; max-width: 600px;">
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 12px; border: 1px solid #ddd; font-weight: bold;">Incident Type:</td>
                    <td style="padding: 12px; border: 1px solid #ddd;">{call.call_type}</td>
                </tr>
                <tr>
                    <td style="padding: 12px; border: 1px solid #ddd; font-weight: bold;">Time:</td>
                    <td style="padding: 12px; border: 1px solid #ddd;">{call.datetime_str}</td>
                </tr>
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 12px; border: 1px solid #ddd; font-weight: bold;">Location:</td>
                    <td style="padding: 12px; border: 1px solid #ddd; color: #d73502; font-weight: bold;">{call.location}</td>
                </tr>
                <tr>
                    <td style="padding: 12px; border: 1px solid #ddd; font-weight: bold;">District:</td>
                    <td style="padding: 12px; border: 1px solid #ddd;">{call.district}</td>
                </tr>
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 12px; border: 1px solid #ddd; font-weight: bold;">Incident Number:</td>
                    <td style="padding: 12px; border: 1px solid #ddd;">{call.incident_number}</td>
                </tr>
            </table>
            
            <p style="margin-top: 20px; padding: 12px; background-color: #fff3cd; border: 1px solid #ffeeba; border-radius: 4px;">
                <strong>Alert Reason:</strong> This call contains "<strong>{config.search_term}</strong>" in the location field.
            </p>
            
            <p style="color: #6c757d; font-size: 12px; margin-top: 20px;">
                This is an automated notification from Orlando PD Monitor.<br>
                Data source: Orlando Police Department Active Calls Feed
            </p>
        </body>
        </html>
        """
        
        text_content = f"""
Orlando PD Alert: {config.search_term}

Incident Type: {call.call_type}
Time: {call.datetime_str}
Location: {call.location}
District: {call.district}
Incident Number: {call.incident_number}

Alert Reason: This call contains "{config.search_term}" in the location field.

---
This is an automated notification from Orlando PD Monitor.
Data source: Orlando Police Department Active Calls Feed
        """
        
        logger.debug(f"Sending email to {', '.join(config.email_to)}")
        
        # Send the email
        params = {
            "from": config.email_from,
            "to": config.email_to,  # Now a list of email addresses
            "subject": subject,
            "html": html_content,
            "text": text_content
        }
        
        response = resend.Emails.send(params)
        
        logger.info(f"📧 Email notification sent successfully for incident {call.incident_number} (ID: {response['id']})")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email notification for incident {call.incident_number}: {e}")
        return False

def process_and_notify_matches(matching_calls: List[PoliceCall], config: Config, tracker: NotificationTracker) -> int:
    """
    Process matching calls and send notifications, preventing duplicates.
    
    Args:
        matching_calls: List of PoliceCall objects that match the search criteria
        config: Configuration object with ntfy settings
        tracker: NotificationTracker to prevent duplicate notifications
        
    Returns:
        Number of notifications actually sent (excluding duplicates)
    """
    logger = logging.getLogger(__name__)
    notifications_sent = 0
    
    if not matching_calls:
        logger.info("No matching calls to process")
        return notifications_sent
    
    logger.info(f"Processing {len(matching_calls)} matching calls...")
    
    for call in matching_calls:
        try:
            # Send ntfy.sh notification
            ntfy_success = send_notification(call, config, tracker)
            
            # Send email notification (only if not a duplicate)
            email_success = False
            if ntfy_success:  # Only send email if ntfy succeeded (not a duplicate)
                email_success = send_email_notification(call, config)
            
            if ntfy_success:
                notifications_sent += 1
                
        except Exception as e:
            logger.error(f"Error processing notifications for incident {call.incident_number}: {e}")
    
    logger.info(f"📊 Summary: {notifications_sent} new notifications sent, {len(matching_calls) - notifications_sent} duplicates skipped")
    logger.info(f"📊 Total incidents tracked: {tracker.get_notification_count()}")
    
    return notifications_sent

def monitor_loop(config: Config, tracker: NotificationTracker) -> None:
    """
    Main monitoring loop that continuously checks for new incidents.
    
    Args:
        config: Configuration object with all settings
        tracker: NotificationTracker to prevent duplicate notifications
    """
    logger = logging.getLogger(__name__)
    loop_count = 0
    consecutive_errors = 0
    max_consecutive_errors = 5
    
    while True:
        try:
            loop_count += 1
            logger.debug(f"🔄 Monitoring loop #{loop_count}")
            
            # Fetch and parse active calls
            raw_data = fetch_active_calls()
            active_calls = parse_active_calls(raw_data)
            
            logger.info(f"📋 Retrieved {len(active_calls)} active calls")
            
            # Search for matching calls
            matching_calls = search_calls_by_location(active_calls, config.search_term)
            
            if matching_calls:
                logger.info(f"🚨 MATCH FOUND! {len(matching_calls)} calls contain '{config.search_term}'")
                
                # Process notifications (will skip duplicates automatically)
                notifications_sent = process_and_notify_matches(matching_calls, config, tracker)
                
                if notifications_sent > 0:
                    logger.info(f"🔔 Sent {notifications_sent} new notifications")
                else:
                    logger.debug("No new notifications (all were duplicates)")
            else:
                logger.debug(f"No calls found containing '{config.search_term}'")
            
            # Reset error counter on successful iteration
            consecutive_errors = 0
            
            # Wait for next polling interval
            logger.debug(f"💤 Sleeping for {config.poll_interval} seconds...")
            time.sleep(config.poll_interval)
            
        except requests.exceptions.RequestException as e:
            consecutive_errors += 1
            logger.error(f"Network error (attempt {consecutive_errors}): {e}")
            
            if consecutive_errors >= max_consecutive_errors:
                logger.error(f"Too many consecutive network errors ({consecutive_errors}). Stopping monitor.")
                raise
            
            # Exponential backoff for network errors
            backoff_time = min(300, 30 * (2 ** (consecutive_errors - 1)))  # Max 5 minutes
            logger.info(f"⏳ Waiting {backoff_time} seconds before retry...")
            time.sleep(backoff_time)
            
        except Exception as e:
            consecutive_errors += 1
            logger.error(f"Unexpected error in monitoring loop (attempt {consecutive_errors}): {e}")
            
            if consecutive_errors >= max_consecutive_errors:
                logger.error(f"Too many consecutive errors ({consecutive_errors}). Stopping monitor.")
                raise
            
            # Wait before retrying
            logger.info(f"⏳ Waiting 60 seconds before retry...")
            time.sleep(60)

def main():
    """Main entry point for the Orlando PD monitor."""
    try:
        # Parse configuration
        config = parse_arguments()
        
        # Setup logging
        setup_logging(verbose='--verbose' in sys.argv or '-v' in sys.argv)
        
        logger = logging.getLogger(__name__)
        logger.info("Orlando PD Monitor starting...")
        logger.info(f"Configuration: Topic={config.ntfy_topic}, Search={config.search_term}, Interval={config.poll_interval}s")
        
        if config.email_enabled:
            recipients = ', '.join(config.email_to)
            logger.info(f"📧 Email notifications enabled: {config.email_from} → {recipients}")
        else:
            logger.info("📧 Email notifications disabled (missing configuration)")
        
        # Initialize notification tracker
        tracker = NotificationTracker()
        logger.info("Notification tracker initialized")
        
        # Start continuous monitoring
        logger.info(f"🔄 Starting continuous monitoring (polling every {config.poll_interval} seconds)")
        logger.info(f"🔍 Searching for '{config.search_term}' in call locations")
        logger.info(f"📡 Notifications will be sent to: {config.ntfy_topic}")
        logger.info("Press Ctrl+C to stop monitoring")
        
        monitor_loop(config, tracker)
        
    except KeyboardInterrupt:
        logging.info("🛑 Monitor stopped by user")
        logging.info(f"📊 Final summary: {tracker.get_notification_count()} total notifications sent during this session")
    except Exception as e:
        logging.error(f"💥 Fatal error: {e}")
        logging.info(f"📊 Final summary: {tracker.get_notification_count()} total notifications sent before error")
        sys.exit(1)

if __name__ == "__main__":
    main() 