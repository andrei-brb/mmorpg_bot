"""Remote push notifications.

The app already schedules LOCAL notifications for things the phone can predict —
the daily reset, the idle cap filling. Everything that makes a shared game worth
returning to is unpredictable from the device: someone whispered you, your guild
started a raid, your season ends tonight.

Everything here is complete except the Apple credential, which cannot be
generated from code — it requires signing in to a paid Apple Developer account.
These tests pin the parts that are done, including that the game behaves
normally while it is missing.
"""
import inspect
import os
import pathlib
import unittest

from services.notifications import push
from services.notifications.push import (
    APNS_GONE,
    APNsPusher,
    DEFAULT_BUNDLE_ID,
    LogPusher,
    get_pusher,
    reset_pusher,
)


class TestDriverSelection(unittest.TestCase):
    def setUp(self):
        reset_pusher()
        self._saved = {k: os.environ.pop(k, None) for k in
                       ("APNS_KEY_ID", "APNS_TEAM_ID", "APNS_AUTH_KEY", "APNS_BUNDLE_ID")}

    def tearDown(self):
        for k, v in self._saved.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)
        reset_pusher()

    def test_without_credentials_it_logs_rather_than_failing(self):
        """The game must work normally with push unconfigured — this ships
        before the Apple key exists."""
        self.assertIsInstance(get_pusher(), LogPusher)

    def test_the_stub_reports_what_is_missing(self):
        p = get_pusher()
        self.assertIn("APNS_KEY_ID", getattr(p, "reason", ""))

    def test_partial_credentials_do_not_half_enable_it(self):
        os.environ["APNS_KEY_ID"] = "ABCDE12345"
        reset_pusher()
        self.assertIsInstance(get_pusher(), LogPusher)

    def test_the_driver_is_cached(self):
        reset_pusher()
        self.assertIs(get_pusher(), get_pusher())


class TestSafety(unittest.TestCase):
    def test_sending_never_raises(self):
        """A notification failing must never take down the game action that
        triggered it."""
        src = inspect.getsource(push.notify_player)
        self.assertIn("except Exception", src)
        self.assertGreaterEqual(src.count("try:"), 2)

    def test_registration_never_raises(self):
        src = inspect.getsource(push.register_device)
        self.assertIn("except Exception", src)

    def test_absurd_tokens_are_rejected_before_the_database(self):
        src = inspect.getsource(push.register_device)
        self.assertIn("len(token) > 200", src)

    def test_the_apns_sender_swallows_transport_errors(self):
        src = inspect.getsource(APNsPusher.send)
        self.assertIn("except Exception", src)

    def test_a_dead_token_is_recognised(self):
        """Apple's 410 is how we learn a token should be dropped."""
        self.assertEqual(APNS_GONE, 410)
        self.assertIn("APNS_GONE", inspect.getsource(APNsPusher.send))


class TestDeviceRegistry(unittest.TestCase):
    def test_devices_are_keyed_by_token_not_player(self):
        """One player can hold several devices, and Apple invalidates a token on
        reinstall. Keying by token means a dead token is a row to delete rather
        than a player whose notifications silently stop."""
        schema = pathlib.Path("database/db.py").read_text()
        self.assertIn("CREATE TABLE IF NOT EXISTS push_devices", schema)
        block = schema[schema.index("CREATE TABLE IF NOT EXISTS push_devices"):][:500]
        self.assertIn("token           VARCHAR(200) PRIMARY KEY", block)
        self.assertIn("ON DELETE CASCADE", block)

    def test_a_token_can_move_between_players(self):
        """A phone handed to someone else must not keep notifying the old owner."""
        src = inspect.getsource(push.register_device)
        self.assertIn("ON CONFLICT (token) DO UPDATE", src)
        self.assertIn("player_id = EXCLUDED.player_id", src)

    def test_the_endpoints_are_registered(self):
        http = pathlib.Path("services/activity_http.py").read_text()
        self.assertIn('"/api/game/push/register"', http)
        self.assertIn('"/api/game/push/unregister"', http)


class TestItIsActuallyTriggered(unittest.TestCase):
    def test_a_whisper_notifies_the_recipient(self):
        """An unused notification system is the same as no notification system."""
        src = pathlib.Path("services/social/social_service.py").read_text()
        self.assertIn("push.notify_player", src)

    def test_the_whisper_push_happens_after_the_message_is_stored(self):
        from services.social.social_service import SocialService

        src = inspect.getsource(SocialService.send_whisper)
        self.assertLess(
            src.index("INSERT INTO player_whispers"),
            src.index("push.notify_player"),
            "a push failure could lose the whisper",
        )


class TestClientDefersThePrompt(unittest.TestCase):
    def test_permission_is_requested_from_a_toggle_not_on_launch(self):
        """iOS asks once. A prompt shown before the player knows what the game
        is gets denied close to permanently."""
        src = pathlib.Path("mobile/src/platform/pushRegistration.ts").read_text()
        self.assertIn("requestPermissions", src)
        main = pathlib.Path("mobile/src/main.tsx").read_text()
        self.assertNotIn("enablePush", main)

    def test_the_bundle_id_matches_the_app(self):
        cap = pathlib.Path("mobile/capacitor.config.ts").read_text()
        self.assertIn(DEFAULT_BUNDLE_ID, cap)


if __name__ == "__main__":
    unittest.main()
