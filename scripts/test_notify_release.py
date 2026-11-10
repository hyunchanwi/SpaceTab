import io
import unittest
from unittest.mock import Mock
import notify_release as notify


class NotifyReleaseTests(unittest.TestCase):
    def test_only_public_feed_bytes_are_posted_without_credentials(self):
        opener = Mock()
        result = io.BytesIO(b'{"accepted":true}')
        opener.open.return_value.__enter__ = Mock(return_value=result)
        opener.open.return_value.__exit__ = Mock(return_value=False)
        self.assertTrue(notify.publish("https://spacetab.owner.workers.dev/publish", b"signed public feed", opener))
        request = opener.open.call_args.args[0]
        self.assertEqual(request.data, b"signed public feed")
        self.assertEqual(request.method, "POST")
        self.assertNotIn("Authorization", request.headers)

    def test_untrusted_endpoints_and_oversized_payloads_are_rejected_before_network(self):
        opener = Mock()
        for url in ["http://owner.workers.dev/publish", "https://127.0.0.1/publish", "https://owner.workers.dev.evil.invalid/publish",
                    "https://key:secret@owner.workers.dev/publish", "https://owner.workers.dev/publish?token=secret"]:
            with self.assertRaises(ValueError):
                notify.publish(url, b"feed", opener)
        for feed in [b"", b"x" * 16385]:
            with self.assertRaises(ValueError):
                notify.publish("https://owner.workers.dev/publish", feed, opener)
        opener.open.assert_not_called()

    def test_redirects_are_not_followed(self):
        self.assertIsNone(notify.NoRedirect().redirect_request(None, None, 302, "redirect", {}, "http://127.0.0.1"))


if __name__ == "__main__":
    unittest.main()
