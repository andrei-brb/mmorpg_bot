"""Regression tests for server-issued session tokens (mobile / standalone auth)."""

from __future__ import annotations

import os
import unittest

# Deterministic signing key for the test process.
os.environ.setdefault("SESSION_JWT_SECRET", "test-secret-key-for-session-tokens")

from services.auth import session_tokens as st


class TestSessionTokens(unittest.TestCase):
    def test_roundtrip_returns_player_id_and_provider(self):
        tok = st.issue_session(123456789, "discord", now=1_000_000)
        claims = st.verify_session(tok, now=1_000_100)
        self.assertIsNotNone(claims)
        self.assertEqual(int(claims["sub"]), 123456789)
        self.assertEqual(claims["prov"], "discord")

    def test_negative_player_id_survives_roundtrip(self):
        # Native-only accounts use negative synthetic ids (Phase 2).
        tok = st.issue_session(-42, "native", now=1_000_000)
        claims = st.verify_session(tok, now=1_000_001)
        self.assertEqual(int(claims["sub"]), -42)

    def test_identity_claims_reconstruct_discord_user_shape(self):
        tok = st.issue_session(
            7, "discord",
            identity={"username": "kira", "global_name": "Kira", "avatar": "abc"},
            now=1_000_000,
        )
        claims = st.verify_session(tok, now=1_000_001)
        user = st.identity_from_claims(claims)
        self.assertEqual(user["id"], "7")
        self.assertEqual(user["username"], "kira")
        self.assertEqual(user["global_name"], "Kira")
        self.assertEqual(user["avatar"], "abc")

    def test_expired_token_rejected(self):
        tok = st.issue_session(1, "discord", ttl_seconds=60, now=1_000_000)
        self.assertIsNone(st.verify_session(tok, now=1_000_061))
        self.assertIsNotNone(st.verify_session(tok, now=1_000_059))

    def test_tampered_payload_rejected(self):
        tok = st.issue_session(1, "discord", now=1_000_000)
        header, payload, sig = tok.split(".")
        # Forge a different payload but keep the original signature.
        forged_payload = st._b64url_encode(b'{"sub":999,"prov":"discord","exp":9999999999}')
        forged = f"{header}.{forged_payload}.{sig}"
        self.assertIsNone(st.verify_session(forged, now=1_000_001))

    def test_wrong_key_rejected(self):
        tok = st.issue_session(1, "discord", now=1_000_000)
        real = st._secret
        try:
            st._secret = lambda: b"a-different-signing-key"  # type: ignore[assignment]
            self.assertIsNone(st.verify_session(tok, now=1_000_001))
        finally:
            st._secret = real

    def test_garbage_tokens_return_none_not_raise(self):
        for bad in ("", "not-a-jwt", "a.b", "a.b.c.d", "...", "x.y.z"):
            self.assertIsNone(st.verify_session(bad))

    def test_discord_bearer_is_not_mistaken_for_a_session_token(self):
        # A raw Discord bearer (opaque, not our JWT) must not verify as a session.
        self.assertIsNone(st.verify_session("mfa.Abcd1234OpaqueDiscordAccessToken"))


if __name__ == "__main__":
    unittest.main()
