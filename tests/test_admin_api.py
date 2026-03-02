import base64
import tempfile
import unittest
from os import environ
from unittest.mock import patch

from fastapi.testclient import TestClient

from newsbot.admin.app import app


class AdminApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile()
        self.client = TestClient(app)
        self.env = {
            "STATE_DB_PATH": self.tmp.name,
            "ADMIN_USERNAME": "admin",
            "ADMIN_PASSWORD": "secret",
            "TG_SOURCE_CHANNELS": "@one,@two",
        }
        self.patcher = patch.dict(environ, self.env, clear=False)
        self.patcher.start()

    def tearDown(self) -> None:
        self.patcher.stop()
        self.tmp.close()

    def test_requires_auth(self):
        response = self.client.get("/api/settings")
        self.assertEqual(response.status_code, 401)

    def test_updates_and_masks_secret(self):
        response = self.client.put(
            "/api/settings/openai-key",
            headers=self._auth_headers(),
            json={"openai_api_key": "sk-test-123456"},
        )
        self.assertEqual(response.status_code, 200)

        snapshot = self.client.get("/api/settings", headers=self._auth_headers())
        self.assertEqual(snapshot.status_code, 200)
        self.assertEqual(snapshot.json()["openai_api_key_masked"], "**********3456")

    def test_add_and_remove_sources(self):
        added = self.client.post(
            "/api/settings/sources",
            headers=self._auth_headers(),
            json={"channel": "@three"},
        )
        self.assertEqual(added.status_code, 200)
        self.assertIn("@three", added.json()["channels"])

        removed = self.client.delete("/api/settings/sources/%40one", headers=self._auth_headers())
        self.assertEqual(removed.status_code, 200)
        self.assertNotIn("@one", removed.json()["channels"])

    def _auth_headers(self) -> dict[str, str]:
        token = base64.b64encode(b"admin:secret").decode("ascii")
        return {"Authorization": f"Basic {token}"}


if __name__ == "__main__":
    unittest.main()
