import unittest
import espn_tables as espn

class League_test(unittest.TestCase):
    def setUp(self):
        self.league = espn.League(13239, 2016, 18)
        