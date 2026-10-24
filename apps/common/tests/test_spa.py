from django.test import TestCase, override_settings


class SpaShellTests(TestCase):
    def test_built_shell_is_served_for_client_routes_and_assets(self):
        dist = self._dist()
        index = "<!doctype html><title>منظومة المتابعة</title>"
        (dist / "index.html").write_text(index, encoding="utf-8")
        assets = dist / "assets"
        assets.mkdir()
        (assets / "app.js").write_text("console.log(1)", encoding="utf-8")
        secret = dist.parent / "secret.txt"
        secret.write_text("nope", encoding="utf-8")

        with override_settings(SPA_DIST=dist):
            home = self.client.get("/")
            complaints = self.client.get("/complaints/")
            login = self.client.get("/login/")
            script = self.client.get("/assets/app.js")
            escaped = self.client.get("/assets/../secret.txt")
            unknown_api = self.client.get("/api/missing/")

        home_body = b"".join(home.streaming_content)
        self.assertEqual(home.status_code, 200)
        self.assertIn("منظومة المتابعة".encode(), home_body)
        self.assertEqual(b"".join(complaints.streaming_content), home_body)
        self.assertEqual(b"".join(login.streaming_content), home_body)
        self.assertEqual(script.status_code, 200)
        self.assertIn(b"console.log", b"".join(script.streaming_content))
        self.assertEqual(b"".join(escaped.streaming_content), home_body)
        self.assertEqual(unknown_api.status_code, 404)
        self.assertEqual(self.client.get("/health/").content, b"ok")

    def test_missing_build_says_the_interface_is_not_built(self):
        with override_settings(SPA_DIST=self._dist()):
            response = self.client.get("/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.content.decode(), "الواجهة غير مبنية.")

    def _dist(self):
        root = self._call_path()
        root.mkdir()
        return root

    def _call_path(self):
        from pathlib import Path
        from tempfile import mkdtemp

        return Path(mkdtemp()) / "dist"
