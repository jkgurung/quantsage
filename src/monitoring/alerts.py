"""
Alert System for trading system notifications.

Monitors risk events and sends alerts via multiple channels:
- Console logging
- File logging
- Email (optional, configurable)
- Future: SMS, Slack, Discord
"""

import logging
from datetime import datetime
from typing import Optional, Dict, List
from enum import Enum

from src.core.events import EventType, RiskAlertEvent, PositionUpdateEvent
from src.core.event_bus import EventBus

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertChannel(Enum):
    """Alert delivery channels."""
    CONSOLE = "console"
    FILE = "file"
    EMAIL = "email"
    SMS = "sms"


class AlertSystem:
    """
    Monitor events and send alerts for important trading system events.

    Features:
    - Subscribe to risk and position events
    - Multi-level alerts (INFO, WARNING, CRITICAL)
    - Multi-channel delivery (console, file, email)
    - Configurable alert rules
    - Alert history tracking
    """

    def __init__(
        self,
        event_bus: EventBus,
        config: Optional[Dict] = None
    ):
        """
        Initialize alert system.

        Args:
            event_bus: EventBus to subscribe to
            config: Optional configuration dict
        """
        self.event_bus = event_bus
        self.config = config or {}

        # Alert configuration
        self.enabled_channels = self.config.get('channels', [AlertChannel.CONSOLE.value, AlertChannel.FILE.value])
        self.email_config = self.config.get('email', {})

        # Alert history
        self.alert_history: List[Dict] = []
        self.max_history = self.config.get('max_history', 1000)

        # Subscribe to events
        self.event_bus.subscribe(EventType.RISK_ALERT, self._on_risk_alert)
        self.event_bus.subscribe(EventType.POSITION_UPDATE, self._on_position_update)

        logger.info(f"AlertSystem initialized with channels: {self.enabled_channels}")

    def _on_risk_alert(self, event: RiskAlertEvent):
        """
        Handle risk alert events.

        Args:
            event: RiskAlertEvent
        """
        # Determine alert level based on risk type
        if event.risk_type in ['CIRCUIT_BREAKER', 'MAX_DRAWDOWN']:
            level = AlertLevel.CRITICAL
        elif event.risk_type in ['DAILY_LOSS_LIMIT', 'POSITION_SIZE_EXCEEDED']:
            level = AlertLevel.WARNING
        else:
            level = AlertLevel.INFO

        # Format message
        message = f"🚨 RISK ALERT: {event.risk_type} - {event.message}"

        # Send alert
        self._send_alert(
            level=level,
            message=message,
            details={
                'event_type': 'RISK_ALERT',
                'risk_type': event.risk_type,
                'symbol': event.symbol,
                'current_value': event.current_value,
                'limit_value': event.limit_value,
                'timestamp': event.timestamp.isoformat()
            }
        )

    def _on_position_update(self, event: PositionUpdateEvent):
        """
        Handle position update events.

        Args:
            event: PositionUpdateEvent
        """
        # Only alert on position opened/closed
        if event.action in ['OPENED', 'CLOSED']:
            level = AlertLevel.INFO

            if event.action == 'OPENED':
                message = f"✅ Position OPENED: {event.side} {event.quantity} {event.symbol} @ ${event.entry_price:.2f}"
            else:
                pnl_emoji = '💰' if event.pnl_realized >= 0 else '📉'
                message = f"{pnl_emoji} Position CLOSED: {event.side} {event.quantity} {event.symbol} | P&L: ${event.pnl_realized:,.2f}"

            self._send_alert(
                level=level,
                message=message,
                details={
                    'event_type': 'POSITION_UPDATE',
                    'action': event.action,
                    'symbol': event.symbol,
                    'side': event.side,
                    'quantity': event.quantity,
                    'pnl_realized': event.pnl_realized,
                    'timestamp': event.timestamp.isoformat()
                }
            )

    def _send_alert(
        self,
        level: AlertLevel,
        message: str,
        details: Optional[Dict] = None
    ):
        """
        Send alert through configured channels.

        Args:
            level: Alert severity level
            message: Alert message
            details: Additional details
        """
        # Store in history
        alert_record = {
            'timestamp': datetime.now().isoformat(),
            'level': level.value,
            'message': message,
            'details': details or {}
        }
        self._add_to_history(alert_record)

        # Send to console
        if AlertChannel.CONSOLE.value in self.enabled_channels:
            self._send_console(level, message)

        # Send to file
        if AlertChannel.FILE.value in self.enabled_channels:
            self._send_file(level, message, details)

        # Send to email (if configured and enabled)
        if AlertChannel.EMAIL.value in self.enabled_channels and self.email_config:
            self._send_email(level, message, details)

    def _send_console(self, level: AlertLevel, message: str):
        """
        Send alert to console.

        Args:
            level: Alert level
            message: Message to log
        """
        if level == AlertLevel.CRITICAL:
            logger.critical(message)
        elif level == AlertLevel.WARNING:
            logger.warning(message)
        else:
            logger.info(message)

        # Also print to stdout for visibility
        print(f"\n[{level.value}] {message}\n")

    def _send_file(self, level: AlertLevel, message: str, details: Optional[Dict]):
        """
        Send alert to file.

        Args:
            level: Alert level
            message: Message
            details: Additional details
        """
        # File logging already handled by logger
        # Could write to separate alerts.log if needed
        pass

    def _send_email(self, level: AlertLevel, message: str, details: Optional[Dict]):
        """
        Send alert via email.

        Args:
            level: Alert level
            message: Message
            details: Additional details
        """
        # Email implementation (requires SMTP configuration)
        # Placeholder for future implementation
        logger.debug(f"Email alert (not configured): {message}")

        # Example implementation (commented out):
        # import smtplib
        # from email.mime.text import MIMEText
        #
        # smtp_host = self.email_config.get('smtp_host')
        # smtp_port = self.email_config.get('smtp_port')
        # from_addr = self.email_config.get('from_address')
        # to_addrs = self.email_config.get('to_addresses', [])
        # password = self.email_config.get('password')
        #
        # if not all([smtp_host, smtp_port, from_addr, to_addrs, password]):
        #     return
        #
        # msg = MIMEText(f"{message}\n\nDetails: {details}")
        # msg['Subject'] = f"[QuantSage Alert] {level.value}: Trading System Alert"
        # msg['From'] = from_addr
        # msg['To'] = ', '.join(to_addrs)
        #
        # try:
        #     with smtplib.SMTP(smtp_host, smtp_port) as server:
        #         server.starttls()
        #         server.login(from_addr, password)
        #         server.send_message(msg)
        #     logger.info("Email alert sent successfully")
        # except Exception as e:
        #     logger.error(f"Failed to send email alert: {e}")

    def _add_to_history(self, alert_record: Dict):
        """
        Add alert to history.

        Args:
            alert_record: Alert record to store
        """
        self.alert_history.append(alert_record)

        # Trim history if too long
        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[-self.max_history:]

    def get_recent_alerts(self, limit: int = 10) -> List[Dict]:
        """
        Get recent alerts.

        Args:
            limit: Maximum number of alerts to return

        Returns:
            List of recent alert records
        """
        return self.alert_history[-limit:]

    def get_alerts_by_level(self, level: AlertLevel, limit: int = 10) -> List[Dict]:
        """
        Get alerts filtered by level.

        Args:
            level: Alert level to filter by
            limit: Maximum number of alerts

        Returns:
            List of filtered alerts
        """
        filtered = [
            alert for alert in self.alert_history
            if alert['level'] == level.value
        ]
        return filtered[-limit:]

    def clear_history(self):
        """Clear alert history."""
        self.alert_history = []
        logger.info("Alert history cleared")
