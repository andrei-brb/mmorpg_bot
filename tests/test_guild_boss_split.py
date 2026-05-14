import unittest
from uuid import uuid4

from services.guild.guild_boss import _split_gold


class TestGuildBossSplit(unittest.TestCase):
    def test_proportional_split(self):
        a, b = uuid4(), uuid4()
        out = _split_gold(1000, {a: 100, b: 300}, min_g=1)
        self.assertEqual(out[a], 250)
        self.assertEqual(out[b], 750)
        self.assertEqual(sum(out.values()), 1000)

    def test_scaled_when_min_g_would_exceed_pool(self):
        a, b = uuid4(), uuid4()
        out = _split_gold(100, {a: 1, b: 1}, min_g=80)
        self.assertLessEqual(sum(out.values()), 100)
        self.assertGreaterEqual(out.get(a, 0), 0)
        self.assertGreaterEqual(out.get(b, 0), 0)


if __name__ == "__main__":
    unittest.main()
