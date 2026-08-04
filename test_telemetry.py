"""
Tests for openMCP anonymous telemetry module.
"""

import os
import time
import unittest
from unittest.mock import patch

from telemetry import (
    SERVER_VERSION,
    is_telemetry_disabled,
    log_telemetry,
    record_telemetry_event,
    register_dataset_resources,
)
from structured_results import make_error_result, make_tool_result
from version import __version__


class TestTelemetry(unittest.TestCase):

    def test_server_version_matches_release_version(self):
        self.assertEqual(SERVER_VERSION, __version__)

    def setUp(self):
        # Clear telemetry env vars before each test
        for var in (
            "OPENDATA_FYI_TELEMETRY_ENABLED",
            "OPENMCP_TELEMETRY_ENABLED",
            "OPENMCP_TELEMETRY_DISABLED",
            "DISABLE_TELEMETRY",
            "TELEMETRY_DB_URL",
            "TELEMETRY_DB_KEY",
        ):
            if var in os.environ:
                del os.environ[var]

    def test_opt_in_check(self):
        self.assertTrue(is_telemetry_disabled())

        os.environ["OPENDATA_FYI_TELEMETRY_ENABLED"] = "true"
        self.assertFalse(is_telemetry_disabled())

        os.environ["OPENMCP_TELEMETRY_DISABLED"] = "true"
        self.assertTrue(is_telemetry_disabled())

    @patch("telemetry._executor.submit")
    def test_record_event_when_enabled(self, mock_submit):
        os.environ["TELEMETRY_DB_URL"] = "https://example.supabase.co/rest/v1/telemetry_events"
        os.environ["TELEMETRY_DB_KEY"] = "test-key"
        os.environ["OPENDATA_FYI_TELEMETRY_ENABLED"] = "true"

        record_telemetry_event(
            tool_name="semantic_search_datasets",
            dataset_ids=[
                "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            ],
            latency_ms=45.2
        )

        mock_submit.assert_called_once()
        args = mock_submit.call_args[0]
        self.assertEqual(args[1], "https://example.supabase.co/rest/v1/telemetry_events")
        self.assertEqual(args[2], "test-key")
        payload = args[3]
        self.assertEqual(
            set(payload),
            {
                "session_id",
                "tool_name",
                "status",
                "error_code",
                "latency_ms",
                "server_version",
                "dataset_ids",
            },
        )
        self.assertEqual(payload["tool_name"], "semantic_search_datasets")
        self.assertEqual(payload["latency_ms"], 45.2)
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["server_version"], SERVER_VERSION)
        self.assertEqual(
            payload["dataset_ids"],
            ["aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"],
        )
        self.assertIsNone(payload["error_code"])

    @patch("telemetry._executor.submit")
    def test_source_qualified_dataset_ids_are_preserved(self, mock_submit):
        os.environ["OPENDATA_FYI_TELEMETRY_ENABLED"] = "true"

        record_telemetry_event(
            tool_name="get_dataset",
            dataset_ids=["alberta:aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"],
        )

        payload = mock_submit.call_args[0][3]
        self.assertEqual(
            payload["dataset_ids"],
            ["alberta:aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"],
        )

    @patch("telemetry._executor.submit")
    def test_record_event_when_disabled(self, mock_submit):
        os.environ["TELEMETRY_DB_URL"] = "https://example.supabase.co/rest/v1/telemetry_events"

        record_telemetry_event(
            tool_name="semantic_search_datasets",
            latency_ms=45.2
        )

        mock_submit.assert_not_called()

    @patch("telemetry.record_telemetry_event")
    def test_decorator_measures_latency_without_capturing_query(self, mock_record):
        @log_telemetry("sample_tool")
        def sample_tool(query: str, limit: int = 5) -> str:
            time.sleep(0.01)
            return f"results for {query}"

        res = sample_tool("housing prices", limit=10)
        self.assertEqual(res, "results for housing prices")

        mock_record.assert_called_once()
        kwargs = mock_record.call_args[1]
        self.assertEqual(kwargs["tool_name"], "sample_tool")
        self.assertGreater(kwargs["latency_ms"], 5.0)
        self.assertEqual(kwargs["status"], "success")
        self.assertEqual(kwargs["dataset_ids"], [])
        self.assertNotIn("question_or_query", kwargs)

    @patch("telemetry.record_telemetry_event")
    def test_selected_dataset_is_associated_with_later_resource_queries(self, mock_record):
        @log_telemetry("query_remote_file")
        def dummy_query_remote_file(file_url: str, sql_query: str) -> str:
            return "ok"

        dataset_id = "abcd1234-ef56-7890-ab12-cd34567890ef"
        resource_id = "99999999-aaaa-bbbb-cccc-dddddddddddd"
        url = "https://example.gc.ca/download/test.csv"
        sql = "SELECT * FROM '{file}' LIMIT 5"
        register_dataset_resources(
            dataset_id,
            [{"id": resource_id, "url": url}],
        )

        dummy_query_remote_file(url, sql)
        mock_record.assert_called_once()
        kwargs = mock_record.call_args[1]
        self.assertEqual(kwargs["tool_name"], "query_remote_file")
        self.assertEqual(kwargs["dataset_ids"], [dataset_id])
        self.assertNotIn("question_or_query", kwargs)
        self.assertNotIn("resource_id", kwargs)

        mock_record.reset_mock()

        dummy_query_remote_file(file_url=url, sql_query=sql)
        mock_record.assert_called_once()
        kwargs = mock_record.call_args[1]
        self.assertEqual(kwargs["tool_name"], "query_remote_file")
        self.assertEqual(kwargs["dataset_ids"], [dataset_id])
        self.assertNotIn("question_or_query", kwargs)
        self.assertNotIn("resource_id", kwargs)

    @patch("telemetry.record_telemetry_event")
    def test_search_results_are_grouped_and_unique_per_tool_call(self, mock_record):
        @log_telemetry("semantic_search_datasets")
        def sample_search() -> str:
            return """
            https://open.canada.ca/data/en/dataset/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee
            https://open.canada.ca/data/en/dataset/ffffffff-1111-2222-3333-444444444444
            https://open.canada.ca/data/en/dataset/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee
            """

        sample_search()

        mock_record.assert_called_once()
        kwargs = mock_record.call_args[1]
        self.assertEqual(kwargs["tool_name"], "semantic_search_datasets")
        self.assertEqual(
            kwargs["dataset_ids"],
            [
                "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "ffffffff-1111-2222-3333-444444444444",
            ],
        )
        self.assertEqual(kwargs["status"], "success")
        self.assertNotIn("question_or_query", kwargs)

    @patch("telemetry.record_telemetry_event")
    def test_error_uses_exception_type_not_message(self, mock_record):
        @log_telemetry("sample_tool")
        def sample_tool() -> None:
            raise ValueError("private error details")

        with self.assertRaises(ValueError):
            sample_tool()

        kwargs = mock_record.call_args[1]
        self.assertEqual(kwargs["status"], "error")
        self.assertEqual(kwargs["error_code"], "ValueError")
        self.assertNotIn("private error details", str(kwargs))

    @patch("telemetry.record_telemetry_event")
    def test_returned_error_uses_normalized_code(self, mock_record):
        @log_telemetry("sample_tool")
        def sample_tool() -> str:
            return "Error reading private-file.csv: sensitive details"

        sample_tool()

        kwargs = mock_record.call_args[1]
        self.assertEqual(kwargs["status"], "error")
        self.assertEqual(kwargs["error_code"], "ToolReturnedError")
        self.assertNotIn("sensitive details", str(kwargs))

    @patch("telemetry.record_telemetry_event")
    def test_structured_results_preserve_dataset_ids_and_error_codes(self, mock_record):
        dataset_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

        @log_telemetry("structured_search")
        def structured_search():
            return make_tool_result(
                "result",
                datasets=[{"id": dataset_id, "title": "Example"}],
            )

        structured_search()
        kwargs = mock_record.call_args[1]
        self.assertEqual(kwargs["dataset_ids"], [dataset_id])
        self.assertEqual(kwargs["status"], "success")

        mock_record.reset_mock()

        @log_telemetry("structured_error")
        def structured_error():
            return make_error_result(
                "temporary failure",
                code="SearchUnavailable",
                retryable=True,
            )

        structured_error()
        kwargs = mock_record.call_args[1]
        self.assertEqual(kwargs["status"], "error")
        self.assertEqual(kwargs["error_code"], "SearchUnavailable")


if __name__ == "__main__":
    unittest.main()
