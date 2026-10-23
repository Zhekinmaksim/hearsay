"""Raw-source transport boundaries; scripted judgments are not live consensus."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_tests import hs, gl, ScriptedModel, fresh, env, write

URL = "https://raw.githubusercontent.com/python/cpython/v3.12.0/Include/patchlevel.h"


class RawSource(unittest.TestCase):
    def setUp(self):
        self.model = ScriptedModel()
        self.c, _ = fresh(self.model)

    def response(self, body=b'#define PY_VERSION "3.12.0"\n', status=200,
                 mime=b"text/plain; charset=utf-8"):
        return SimpleNamespace(body=body, status=status, headers={"content-type": mime})

    def test_raw_bytes_use_independent_strict_equivalence_without_render(self):
        with patch.object(gl.nondet.web, "get", create=True, return_value=self.response()) as get, \
             patch.object(gl.nondet.web, "render", side_effect=AssertionError("browser called")), \
             patch.object(gl.eq_principle, "strict_eq", wraps=gl.eq_principle.strict_eq) as strict, \
             patch.object(gl.eq_principle, "prompt_comparative", side_effect=AssertionError("comparative called")):
            self.assertEqual(self.c._fetch(URL), '#define PY_VERSION "3.12.0"\n')
            get.assert_called_once_with(URL)
            strict.assert_called_once()

    def test_http_errors_and_non_plain_content_are_not_evidence(self):
        for response in (self.response(status=404), self.response(status=302),
                         self.response(mime=b"text/html"), self.response(mime=b"application/octet-stream"),
                         self.response(body=None), self.response(body=b"\xff")):
            with self.subTest(response=response), patch.object(gl.nondet.web, "get", create=True, return_value=response):
                self.assertEqual(self.c._fetch(URL), "")

    def test_utf8_and_existing_source_bound_are_preserved(self):
        text = "Привет 世界\n" * 2000
        with patch.object(gl.nondet.web, "get", create=True,
                          return_value=self.response(text.encode(), mime="Text/Plain; charset=utf-8")):
            self.assertEqual(self.c._fetch(URL), text[:hs.MAX_SOURCE])

    def test_origin_lookalikes_do_not_enter_raw_path(self):
        for url in ("https://raw.githubusercontent.com.evil.example/file",
                    "https://raw.githubusercontent.com@evil.example/file",
                    "http://raw.githubusercontent.com/python/file"):
            with self.subTest(url=url), patch.object(gl.nondet.web, "get", create=True,
                                                     side_effect=AssertionError("raw called")), \
                 patch.object(gl.nondet.web, "render", return_value="Rendered text") as render:
                self.assertEqual(self.c._fetch(url), "Rendered text")
                render.assert_called_once_with(url, mode="text")

    def test_strict_disagreement_fails_closed(self):
        with patch.object(gl.eq_principle, "strict_eq", side_effect=RuntimeError("disagreement")):
            self.assertEqual(self.c._fetch(URL), "")

    def test_network_error_does_not_reach_support_judgments(self):
        with patch.object(gl.nondet.web, "get", create=True, side_effect=TimeoutError("offline")):
            eid = write(self.c, self.model, env("Python version is 3.12.0", source=URL))
        result = self.c.get_entry(eid)
        self.assertEqual(result["status"], hs.UNSOURCED)
        self.assertEqual(result["rounds"], 0)
        self.assertEqual(self.model.seen, [])

    def test_transport_does_not_bypass_the_two_support_framings(self):
        self.model.support = (True, None)
        with patch.object(gl.nondet.web, "get", create=True, return_value=self.response()):
            eid = write(self.c, self.model, env("Python version is 3.12.0", source=URL))
        result = self.c.get_entry(eid)
        self.assertEqual(result["status"], hs.INCONCLUSIVE)
        self.assertEqual(result["votes"]["a"], "yes")
        self.assertEqual(result["votes"]["b"], "unread")
        self.assertEqual(len(self.model.seen), 2)


if __name__ == "__main__":
    unittest.main()
