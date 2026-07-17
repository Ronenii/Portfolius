"""Tests for app/main.py startup hooks and error handling."""

from unittest.mock import MagicMock, Mock, patch

from app.main import run_startup_historical_return_bootstrap


def test_startup_bootstrap_catches_and_logs_exceptions_from_outer_path() -> None:
    """Test that exceptions in the outer bootstrap path are caught and logged.

    This regression test ensures that if bootstrap_historical_returns_if_never_run
    or its dependencies (DB session setup, market_data_client construction,
    historical_returns_never_computed query) raise an exception, that exception
    is caught and logged instead of propagating uncaught into asyncio's task
    exception handler (where it would only surface as a generic warning at
    garbage-collection time).
    """
    # Mock SessionLocal to return a mock session
    mock_session = MagicMock()

    # Mock the logger so we can verify it's called
    mock_logger = Mock()

    with patch("app.main.SessionLocal") as mock_session_local, patch(
        "app.main.get_market_data_client"
    ), patch(
        "app.main.bootstrap_historical_returns_if_never_run"
    ) as mock_bootstrap, patch(
        "app.main.logging.getLogger", return_value=mock_logger
    ):
        mock_session_local.return_value = mock_session

        # Force bootstrap to raise an exception (simulating a DB connectivity
        # hiccup or other transient failure in the outer path)
        test_error = RuntimeError("Database connection failed at startup")
        mock_bootstrap.side_effect = test_error

        # This should NOT raise; the exception should be caught and logged
        run_startup_historical_return_bootstrap()

        # Verify the session was opened and closed
        mock_session_local.assert_called_once()
        mock_session.close.assert_called_once()

        # Verify the logger.exception() was called with the expected message
        mock_logger.exception.assert_called_once_with(
            "Historical return startup bootstrap failed"
        )
