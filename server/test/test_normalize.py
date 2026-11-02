import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'zbieracz'))
from normalize import money, parse_base_price, parse_pack, parse_valid, unit_price, verify  # noqa: E402
import kaufland  # noqa: E402

TODAY = dt.date(2026, 11, 2)
V = 'Oferta ważna od 29.10. do 04.11.'


class Pack(unittest.TestCase):
    def test_cases(self):
        c = {
            '2 x 2 l opakowanie': (4, 'l', 'ok'), '1 kg': (1, 'kg', 'ok'), '500 g opakowanie': (500, 'g', 'ok'),
            '8 x 100 g opakowanie': (800, 'g', 'ok'), '4 x 0,5 l puszka 2 l opakowanie': (2, 'l', 'ok'),
            '400 g + 50 g sos opakowanie': (450, 'g', 'ok'), '450/420 g opakowanie': (450, 'g', 'check'),
            '181-165 g opakowanie': (181, 'g', 'check'), '0,75 l butelka': (0.75, 'l', 'ok'), '420g': (420, 'g', 'ok'),
            '32 szt. opakowanie': (32, 'szt', 'ok'), '5 sztuk opakowanie': (5, 'szt', 'ok'), 'sztuka': (1, 'szt', 'ok'),
            '10 m sztuka': (1, 'szt', 'ok'), '100 g': (100, 'g', 'ok'),
        }
        for t, (a, u, conf) in c.items():
            p = parse_pack(t)
            self.assertIsNotNone(p, t)
            self.assertEqual((round(p['amount'], 4), p['unit'], p['conf']), (a, u, conf), t)
        self.assertIsNone(parse_pack('opakowanie'))

    def test_money(self):
        self.assertEqual(money('13,98'), 1398)
        self.assertEqual(money('1 299,00'), 129900)
        self.assertEqual(money('4,99cena przed obniżką'), 499)
        self.assertIsNone(money('tylko'))

    def test_base(self):
        self.assertEqual(parse_base_price('1 kg 19,98'), ('kg', 1998.0))
        self.assertEqual(parse_base_price('(=100 g 0,82)')[0], 'kg')
        self.assertAlmostEqual(parse_base_price('100 g 0,82')[1], 820.0)
        self.assertEqual(parse_base_price('1 l 3,50'), ('l', 350.0))
        self.assertIsNone(parse_base_price('100 g 1,00/1,07'))

    def test_valid(self):
        self.assertEqual(parse_valid(V, TODAY), ('2026-10-29', '2026-11-04'))
        self.assertEqual(parse_valid('Oferta ważna 02.11.', TODAY), ('2026-11-02', '2026-11-02'))
        self.assertEqual(parse_valid('Oferta ważna od 28.12. do 03.01.', dt.date(2027, 1, 2)), ('2026-12-28', '2027-01-03'))
        self.assertEqual(parse_valid('Oferta ważna od 28.12. do 03.01.', dt.date(2026, 12, 29)), ('2026-12-28', '2027-01-03'))
        self.assertEqual(parse_valid('', TODAY), (None, None))


class Kaufland(unittest.TestCase):
    # Prawdziwe wiersze z oferty z 2026-11-02 (sekcja, ważność, marka, nazwa, opakowanie, cena/jedn., rabat, cena, przed, karta)
    ROWS = [
        ['Napoje', V, 'Coca-Cola,', 'Fanta, Sprite Napój gazowany', '2 x 2 l opakowanie', '1 l 3,50', 'tylko', '13,98', '', 0],
        ['Hity tygodnia', 'Oferta ważna 02.11.', 'Mąka Szymanowska pszenna', 'typ 480', '2 kg opakowanie', '1 kg 2,00', '-55%', '3,99', '8,99', 0],
        ['Hity tygodnia', 'Oferta ważna 02.11.', 'Actimel', 'Napój probiotyczny', '8 x 100 g opakowanie', '1 kg 13,49', '-40%', '10,79', '17,99', 0],
        ['Garmażeria, Konserwy', V, 'Kotlin', 'Ketchup', '450/420 g opakowanie', '100 g 1,00/1,07', 'tylko', '4,49', '', 0],
        ['Garmażeria, Konserwy', V, 'Morliny', 'Kebab z kurczaka', '400 g + 50 g sos opakowanie', '1 kg 26,64', '-20%', '11,99', '14,99', 0],
        ['Mięso, Drób, Wędliny', V, 'Skrzydła z kurczaka', '', '1 kg', '', 'tylko', '6,99', '', 0],
        ['Mięso, Drób, Wędliny', V, 'Indykpol', 'Pierś wędzona', '100 g', '1 kg 29,90', '-30%', '2,99', '4,29', 0],
        ['Napoje', V, 'Tyskie Gronie', 'Piwo 5,2% alk.', '4 x 0,5 l puszka 2 l opakowanie', '1 l 5,98', 'tylko', '11,96', '', 0],
        ['Tanio z Kaufland Card XTRA', 'Oferta ważna 02.11.', 'MillWash', 'Kapsułki do zmywarki', '32 szt. opakowanie', '1 szt 0,47', '-50%', '29,99', '59,98', 1],
        ['Napoje', V, 'Dafi', 'Koncentrat napoju 0,5 L', '', '1 szt 14,99', 'tylko', '14,99', '', 0],
        ['Artykuły AGD 22.10.2026 - 04.11.2026', V, 'SilverCrest', 'Robot kuchenny', '', '1 szt 139,00', 'tylko', '139,00', '', 1],
        ['Napoje', V, 'Coca-Cola,', 'Fanta, Sprite Napój gazowany', '2 x 2 l opakowanie', '1 l 3,50', 'tylko', '13,98', '', 0],  # duplikat
        ['Napoje', '', 'Bez daty', 'Woda', '1 l', '', 'tylko', '1,00', '', 0],
    ]

    def setUp(self):
        self.offers, self.warns = kaufland.parse_rows(self.ROWS, TODAY)
        self.by = {o['name']: o for o in self.offers}

    def test_counts(self):
        self.assertEqual(len(self.offers), 10)  # bez AGD, bez duplikatu, bez wiersza bez daty
        self.assertEqual(len(self.warns), 1)

    def test_cola(self):
        o = self.by['Coca-Cola, Fanta, Sprite Napój gazowany']
        self.assertEqual((o['price'], o['amount'], o['unit'], o['conf']), (1398, 4.0, 'l', 'ok'))
        self.assertEqual((o['from'], o['until'], o['store']), ('2026-10-29', '2026-11-04', 'Kaufland'))
        self.assertAlmostEqual(unit_price(o['price'], o['amount'], o['unit'])[1], 349.5)

    def test_verification(self):
        self.assertEqual(self.by['Kotlin Ketchup']['conf'], 'check')  # warianty wagi
        self.assertEqual(self.by['MillWash Kapsułki do zmywarki']['conf'], 'check')  # cena/jedn. sklepu się nie zgadza
        self.assertIn('wg sklepu', self.by['MillWash Kapsułki do zmywarki']['note'])
        for n in ['Morliny Kebab z kurczaka', 'Actimel Napój probiotyczny', 'Indykpol Pierś wędzona', 'Skrzydła z kurczaka', 'Tyskie Gronie Piwo 5,2% alk.']:
            self.assertEqual(self.by[n]['conf'], 'ok', n)

    def test_old_price_and_card(self):
        o = self.by['Mąka Szymanowska pszenna typ 480']
        self.assertEqual((o['price'], o['old'], o['from'], o['until']), (399, 899, '2026-11-02', '2026-11-02'))
        self.assertEqual(self.by['MillWash Kapsułki do zmywarki']['cond'], 'z kartą Kaufland Card XTRA')

    def test_name_pack_fallback(self):
        o = self.by['Dafi Koncentrat napoju 0,5 L']
        self.assertEqual((o['amount'], o['unit']), (0.5, 'l'))


if __name__ == '__main__':
    unittest.main()
