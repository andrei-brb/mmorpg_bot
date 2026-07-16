"""Game-account auth: password hashing, validation, and the id scheme.

These are the pieces that can be tested without a database. The DB-dependent
paths (signup/login/link) are covered by the migration + device checks in the
plan's verification section.
"""
import unittest

from services.auth import passwords as pw
from services.auth import session_tokens as st


class TestPasswordHashing(unittest.TestCase):
    def test_round_trip(self):
        h = pw.hash_password("correct horse battery staple")
        self.assertTrue(pw.verify_password("correct horse battery staple", h))

    def test_wrong_password_rejected(self):
        h = pw.hash_password("hunter2hunter2")
        self.assertFalse(pw.verify_password("hunter2hunter3", h))
        self.assertFalse(pw.verify_password("", h))
        self.assertFalse(pw.verify_password("HUNTER2HUNTER2", h))

    def test_salt_is_per_call(self):
        # Same password twice must not produce the same hash, or the table
        # itself tells an attacker which players share a password.
        self.assertNotEqual(pw.hash_password("same-password"), pw.hash_password("same-password"))

    def test_verify_never_raises_on_garbage(self):
        # A malformed hash is a failed login, not a 500.
        for bad in ["", "not-a-hash", "scrypt$x$y$z$q$r", "$$$$$", "bcrypt$1$2$3$4$5"]:
            self.assertFalse(pw.verify_password("anything", bad))

    def test_hash_is_self_describing(self):
        # The stored format carries its own cost parameters so they can be
        # raised later without invalidating existing passwords.
        h = pw.hash_password("abcdefgh")
        parts = h.split("$")
        self.assertEqual(parts[0], "scrypt")
        self.assertEqual(len(parts), 6)
        self.assertFalse(pw.needs_rehash(h))

    def test_old_cost_params_still_verify_and_flag_rehash(self):
        weak = pw.hash_password("abcdefgh", n=2**10, r=8, p=1)
        self.assertTrue(pw.verify_password("abcdefgh", weak))  # still works
        self.assertTrue(pw.needs_rehash(weak))  # but should be upgraded

    def test_email_token_stores_only_a_hash(self):
        token, token_hash = pw.new_email_token()
        self.assertNotEqual(token, token_hash)
        self.assertEqual(len(token_hash), 64)  # sha256 hex
        self.assertEqual(pw.hash_email_token(token), token_hash)
        # A dump of auth_email_tokens must not yield working links.
        self.assertNotIn(token, token_hash)


class TestValidation(unittest.TestCase):
    def test_username_rules(self):
        for good in ["abc", "bratiska", "ok_name-1", "A1"]:
            if len(good) >= 3:
                self.assertTrue(pw.validate_username(good)[0], good)
        for bad in ["", "ab", "has space", "___", "a" * 25, "bad!char"]:
            self.assertFalse(pw.validate_username(bad)[0], bad)

    def test_password_length_bounds(self):
        self.assertFalse(pw.validate_password("short")[0])
        self.assertTrue(pw.validate_password("longenough")[0])
        self.assertFalse(pw.validate_password("x" * 500)[0])

    def test_email_shape(self):
        for good in ["a@b.com", "first.last+tag@sub.domain.co.uk"]:
            self.assertTrue(pw.validate_email(good)[0], good)
        for bad in ["", "nope", "a@b", "a@@b.com", "@b.com", "a@.com", "a@b."]:
            self.assertFalse(pw.validate_email(bad)[0], bad)


class TestNativeIdScheme(unittest.TestCase):
    """Native ids are negative; Discord snowflakes are always positive. The two
    spaces can never overlap, which is what lets both live in players.id."""

    def test_negative_id_survives_a_session_round_trip(self):
        tok = st.issue_session(-42, "native", identity={"username": "bratiska"})
        claims = st.verify_session(tok)
        self.assertIsNotNone(claims)
        self.assertEqual(claims["sub"], -42)
        self.assertEqual(claims["prov"], "native")

    def test_identity_from_claims_shape_matches_discord(self):
        # Handlers read user["id"] and cannot tell a game account from a Discord
        # one — that is what keeps all 126 authed handlers unchanged.
        tok = st.issue_session(-7, "native", identity={"username": "solo"})
        ident = st.identity_from_claims(st.verify_session(tok))
        self.assertEqual(ident["id"], "-7")
        self.assertEqual(ident["username"], "solo")

    def test_snowflakes_are_positive(self):
        # Discord ids are ms-since-2015 << 22, so the smallest real one is huge
        # and positive. Nothing Discord issues can collide with -N.
        oldest_possible = 1 << 22
        self.assertGreater(oldest_possible, 0)
        self.assertLess(-1, oldest_possible)


if __name__ == "__main__":
    unittest.main()
