import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from importlib.metadata import PackageNotFoundError
from unittest.mock import patch

from coverwise import doctor


class DoctorFailureTests(unittest.TestCase):
    def test_missing_distribution_returns_actionable_failure(self):
        output = io.StringIO()
        with (
            patch.object(
                doctor, "version", side_effect=PackageNotFoundError("uagents")
            ),
            redirect_stdout(output),
            redirect_stderr(output),
        ):
            result = doctor.main()
        self.assertEqual(result, 1)
        self.assertIn("INCOMPATIBLE", output.getvalue())
        self.assertIn("uv sync --locked --dev", output.getvalue())

    def test_wrong_sdk_version_fails_before_chat_import(self):
        output = io.StringIO()
        with (
            patch.object(doctor, "version", return_value="0.0.0"),
            redirect_stdout(output),
            redirect_stderr(output),
        ):
            result = doctor.main()
        self.assertEqual(result, 1)
        self.assertIn("expected uagents==0.25.5", output.getvalue())
