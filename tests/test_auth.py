import base64
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest

spec = importlib.util.spec_from_file_location("launch", Path(__file__).parents[1] / "images/common/launch.py")
launch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launch)


def token(**overrides):
    claims = dict(tid="test-tenant", aud=launch.AUDIENCE, exp=time.time() + 3600)
    claims.update(overrides)
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return "test." + payload + ".not-a-real-signature"


class AuthenticationTests(unittest.TestCase):
    def test_tenant_configuration_is_required(self):
        with self.assertRaisesRegex(ValueError, "FOUNDRY_TENANT_ID"):
            launch.checked_token({"FOUNDRY_AUTH_TOKEN": token()})

    def test_claude_uses_configured_resource_and_deployments(self):
        env = {"FOUNDRY_RESOURCE": "example-foundry", "CLAUDE_MODEL": "primary-deployment",
               "CLAUDE_OPUS_MODEL": "opus-deployment", "CLAUDE_SONNET_MODEL": "sonnet-deployment",
               "CLAUDE_HAIKU_MODEL": "haiku-deployment"}
        launch.configure("claude", env)
        self.assertEqual(env["ANTHROPIC_FOUNDRY_RESOURCE"], "example-foundry")
        self.assertEqual(env["ANTHROPIC_MODEL"], "primary-deployment")
        self.assertEqual(env["ANTHROPIC_DEFAULT_HAIKU_MODEL"], "haiku-deployment")

    def test_resource_url_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "account name"):
            launch.configure("claude", {"FOUNDRY_RESOURCE": "https://unexpected.example"})

    def test_accept_correct_tenant_audience(self):
        value = token()
        self.assertEqual(launch.checked_token({"FOUNDRY_AUTH_TOKEN": value, "FOUNDRY_TENANT_ID": "test-tenant"}), value)

    def test_reject_wrong_tenant_wrong_scope_expired_and_key(self):
        for value in (token(tid="wrong"), token(aud="https://management.azure.com"),
                      token(exp=time.time() - 1), "not-a-jwt", token(exp=None)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                launch.checked_token({"FOUNDRY_AUTH_TOKEN": value, "FOUNDRY_TENANT_ID": "test-tenant"})

    def test_file_refresh_is_read_on_each_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "token"
            path.write_text(token(exp=time.time() - 1))
            with self.assertRaises(ValueError):
                launch.checked_token({"FOUNDRY_TOKEN_FILE": str(path), "FOUNDRY_TENANT_ID": "test-tenant"})
            fresh = token()
            path.write_text(fresh)
            self.assertEqual(launch.checked_token({"FOUNDRY_TOKEN_FILE": str(path), "FOUNDRY_TENANT_ID": "test-tenant"}), fresh)

    def test_missing_file_is_clear_and_does_not_disclose_value(self):
        with self.assertRaisesRegex(ValueError, "Provide FOUNDRY_AUTH_TOKEN"):
            launch.checked_token({"FOUNDRY_TOKEN_FILE": "/nonexistent/foundry-token"})


if __name__ == "__main__":
    unittest.main()
