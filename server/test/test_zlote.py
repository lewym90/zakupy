"""Złote przypadki z prawdziwych stron gazetki Lidl (gazetka-02-11-pon-kw45, str. 10-11).
Wyniki muszą być dokładne. Sprawdzamy też typowe pomyłki modelu: oferta nie może pokazać błędnej ceny za litr jako pewnej."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'zbieracz'))
import lidl  # noqa: E402
from normalize import parse_anchor, parse_pack_parts  # noqa: E402


def up(o):
    """Cena za jednostkę tak, jak liczy aplikacja (js/offers.js: offerCalc)."""
    f = {'g': .001, 'ml': .001}.get(o['unit'], 1)
    total = o['price'] if o['mode'] == 'bundle' else o['price'] * o['need'] if o['mode'] == 'unit' else o['price'] * (o['need'] - 1) + o['price'] * (1 - o['pct'] / 100)
    return round(total / (o['amount'] * f * o['need']))


def m(**k):
    return lidl.map_item(dict({'nazwa': 'Produkt'}, **k), '2026-11-02', '2026-11-08')


COLA2 = dict(nazwa='Coca-Cola', opakowanie='Dwusztuk 2 x 1 L', cena='9,98', cena_dodatkowa='2 x 4,99 zł za butelkę', cena_jednostkowa='1 L = 4,99', kaucja='kaucja 1,00 zł')
COLA4 = dict(nazwa='Coca-Cola', opakowanie='Czterosztuk 4 x 2 L', cena='31,96', cena_dodatkowa='4 x 7,99 zł za butelkę', cena_jednostkowa='1 L = 4,00', kaucja='kaucja 2,00 zł')
ZYWIEC = dict(nazwa='Woda Żywiec Zdrój', opakowanie='Sześciosztuk 6 x 1,5 L', cena='10,74', cena_dodatkowa='6 x 1,79 zł za butelkę', cena_jednostkowa='1 L = 1,19', kaucja='kaucja 3,00 zł')


class Zlote(unittest.TestCase):
    def sprawdz(self, o, need, amount, total, cena_l, kaucja):
        self.assertEqual((o['conf'], o['mode'], o['need'], o['amount'], o['unit'], o['price']), ('ok', 'bundle', need, amount, 'l', total))
        self.assertAlmostEqual(up(o), cena_l, delta=1)
        self.assertEqual(o['deposit'], kaucja)

    def test_dwusztuk(self):
        self.sprawdz(m(**COLA2), 2, 1.0, 998, 499, 100)
        self.assertEqual(m(**COLA2)['promo'], 'Dwusztuk')

    def test_czterosztuk(self):
        self.sprawdz(m(**COLA4), 4, 2.0, 3196, 400, 200)

    def test_szesciosztuk(self):
        self.sprawdz(m(**ZYWIEC), 6, 1.5, 1074, 119, 300)

    def test_2_plus_1_gratis_z_kuponem(self):
        o = m(nazwa='Pepsi Zero', opakowanie='2 L', cena='10,15', cena_jednostkowa='1 L = 5,08', kaucja='kaucja 0,50 zł', promocja='2 + 1 gratis',
              warunek='aktywuj kupon w aplikacji Lidl Plus, limit 1 but. gratis na kupon')
        self.assertEqual((o['conf'], o['need'], o['pay'], o['amount'], o['price'], o['promo']), ('ok', 3, 2, 2.0, 2030, '2 + 1 gratis'))
        self.assertAlmostEqual(up(o), 338, delta=1)
        self.assertIn('Lidl Plus', o['cond'])


class PrawdziwyOdczyt(unittest.TestCase):
    """Dokładnie tak Gemini przepisało te oferty z gazetki kw45."""

    def test_2_plus_1_cena_jednostkowa_w_polu_dodatkowym(self):
        o = m(nazwa='Pepsi Zero, Mirinda, 7UP', opakowanie='2 L', cena='10,15', cena_dodatkowa='Cena poza promocją: 10,15/but., 1 L = 5,08', kaucja='kaucja 0,50 zł', promocja='2 + 1 gratis')
        self.assertEqual((o['conf'], o['need'], o['pay'], o['price']), ('ok', 3, 2, 2030))
        self.assertAlmostEqual(up(o), 338, delta=1)

    def test_8_plus_4_gratis(self):
        o = m(nazwa='Żywiec Jasne Pełne', opakowanie='500 ml', cena='4,39', cena_dodatkowa='Cena poza promocją: 4,39/pusz., 1 L = 8,78', promocja='8 + 4 gratis')
        self.assertEqual((o['conf'], o['need'], o['pay'], o['price']), ('ok', 12, 8, 3512))

    def test_rowno_1_kg_lub_100_g_bez_ceny_jednostkowej(self):
        for pack, cena, wynik in [('1 kg', '69,99', 6999), ('100 g', '8,99', 8990), ('1 L', '4,99', 499)]:
            o = m(nazwa='X', opakowanie=pack, cena=cena)
            self.assertEqual((o['conf'], up(o)), ('ok', wynik), pack)
        self.assertEqual(m(nazwa='X', opakowanie='150 g', cena='8,99')['conf'], 'check')  # inna wielkość nadal wymaga potwierdzenia
        self.assertEqual(m(nazwa='X', opakowanie='2 L', cena='8,99')['conf'], 'check')

    def test_pelne_opakowanie_z_promocja(self):
        o = m(nazwa='Fin Carré Czekolada', opakowanie='100 g', cena='4,49', cena_dodatkowa='Cena poza promocją: 4,49/opak.', promocja='3 za 2')
        self.assertEqual((o['conf'], o['need'], o['pay'], o['price']), ('ok', 3, 2, 898))
        self.assertEqual(m(nazwa='Ogórek', opakowanie='1 szt.', cena='2,39')['conf'], 'ok')

    def test_cena_jednostkowa_sprzed_obnizki(self):
        o = m(nazwa='Cytryny, luzem', opakowanie='1 kg', cena='4,99', cena_dodatkowa='* cena przed obniżką: 1 kg = 11,99', cena_jednostkowa='1 kg = 11,99')
        self.assertEqual((o['conf'], up(o)), ('ok', 499))
        self.assertEqual(m(nazwa='X', opakowanie='1 kg', cena='4,99', cena_jednostkowa='1 kg = 11,99')['conf'], 'check')  # bez takiego napisu to niezgodność

    def test_przypis_ze_skosnikiem_nie_psuje_ceny(self):
        o = m(nazwa='Alpro Napój', opakowanie='750 ml', cena='7,99', cena_jednostkowa='1 L = 10,65\n* najniższa cena\nz 30 dni przed obniżką/')
        self.assertEqual((o['conf'], up(o)), ('ok', 1065))

    def test_warianty_wielkosci_potwierdzone_cena(self):
        for pack, unit, cena in [('50 g, 55 g', '100 g = 13,98/12,71', '6,99'), ('90 g, 100 g', '100 g = 9,99/8,99', '8,99'), ('15-18 g', '100 g = 59,93-49,94', '8,99'), ('15 szt., 20 szt.', '1 szt. = 0,33/0,25', '4,99')]:
            self.assertEqual(m(nazwa='X', opakowanie=pack, cena=cena, cena_jednostkowa=unit)['conf'], 'cena', pack)
        self.assertEqual(m(nazwa='X', opakowanie='50 g, 55 g', cena='3,00', cena_jednostkowa='100 g = 13,98/12,71')['conf'], 'check')

    def test_cena_jednostkowa_sasiedniej_oferty_nie_przechodzi(self):
        self.assertEqual(m(nazwa='Orzechy', opakowanie='150 g', cena='17,49', cena_jednostkowa='100 g = 5,33')['conf'], 'check')

    def test_warianty_nadal_nie_sa_kotwica(self):
        self.assertIsNone(parse_anchor('1 kg = 31,96/34,74'))

    def test_marka_nie_dubluje_sie(self):
        self.assertEqual(m(marka='Pepsi', nazwa='Pepsi Zero', opakowanie='2 L', cena='5,00', cena_jednostkowa='1 L = 2,50')['name'], 'Pepsi Zero')


class PomylkiModelu(unittest.TestCase):
    """Te same oferty, ale model przepisał je gorzej. Wynik ma być poprawny albo oznaczony jako niepewny, nigdy błędny i pewny."""

    def test_kaucja_w_tekscie_ceny_jednostkowej(self):
        c = dict(COLA2, cena_jednostkowa='1 L = 4,99 + kaucja 1,00 zł', kaucja=None)
        self.assertEqual((m(**c)['conf'], up(m(**c)), m(**c)['deposit']), ('ok', 499, 100))

    def test_kaucja_nie_jest_cena(self):
        c = dict(COLA2, cena_dodatkowa='kaucja 1,00 zł', kaucja=None)
        o = m(**c)
        self.assertEqual((o['conf'], o['need'], o['price'], up(o)), ('ok', 2, 998, 499))

    def test_cena_sztuki_zamiast_kompletu(self):
        o = m(**dict(COLA2, cena='4,99', cena_dodatkowa=None))
        self.assertEqual((o['conf'], o['need'], o['price'], up(o)), ('ok', 2, 998, 499))

    def test_opakowanie_bez_mnoznika_ale_z_linia_ceny(self):
        o = m(**dict(COLA4, opakowanie='2 L'))
        self.assertEqual((o['conf'], o['need'], o['amount'], up(o)), ('ok', 4, 2.0, 400))

    def test_opakowanie_jako_suma_kompletu(self):
        o = m(**dict(COLA4, opakowanie='8 L'))
        self.assertEqual((o['conf'], o['need'], o['amount'], up(o)), ('ok', 4, 2.0, 400))

    def test_bledna_cena_jednostkowa_nie_przechodzi(self):
        o = m(**dict(COLA2, cena_jednostkowa='1 L = 9,99'))
        self.assertEqual((o['conf'], o['need'], o['mode'], o['price']), ('check', 1, 'unit', 998))

    def test_brak_ceny_jednostkowej_ale_druk_spojny(self):
        o = m(**dict(COLA2, cena_jednostkowa=None))
        self.assertEqual((o['conf'], up(o)), ('ok', 499))

    def test_brak_kontroli_to_niepewne(self):
        o = m(nazwa='Coca-Cola 2 x 1 L', cena='9,98')
        self.assertEqual(o['conf'], 'check')


class Inne(unittest.TestCase):
    def test_opakowanie_zbiorcze_to_nie_promocja(self):
        o = m(nazwa='Jogurt', opakowanie='4 x 125 g', cena='3,99', cena_jednostkowa='1 kg = 7,98')
        self.assertEqual((o['conf'], o['mode'], o['need'], o['amount'], o['unit']), ('ok', 'unit', 1, 500.0, 'g'))
        self.assertNotIn('promo', o)

    def test_n_za_cene_gdy_opakowanie_ma_ten_sam_mnoznik(self):
        o = m(nazwa='Cola', opakowanie='3 x 1,5 l', cena='9,99', cena_jednostkowa='1 l = 2,22', promocja='3 za 9,99 zł')
        self.assertEqual((o['conf'], o['need'], o['amount'], up(o)), ('ok', 3, 1.5, 222))

    def test_towar_na_wage(self):
        o = m(nazwa='Schab', cena='19,98', cena_jednostkowa='1 kg = 19,98')
        self.assertEqual((o['conf'], o['amount'], o['unit'], o['price']), ('ok', 1.0, 'kg', 1998))

    def test_zwykla_oferta_i_100_g(self):
        o = m(nazwa='Ser', opakowanie='150 g', cena='4,99', cena_jednostkowa='100 g = 3,33')
        self.assertEqual(o['conf'], 'ok')

    def test_parsery(self):
        self.assertEqual(parse_anchor('1 L = 1,19 + kaucja 3,00 zł'), {'base': 'l', 'up': 119.0, 'deposit': 300})
        self.assertEqual(parse_anchor('1 kg 31,96/34,74'), None)
        self.assertEqual(parse_anchor('4,99 zł/1 l')['up'], 499.0)
        self.assertEqual(parse_pack_parts('Czterosztuk 4 x 2 L')['count'], 4)
        self.assertEqual(parse_pack_parts('Dwusztuk 1 L')['count'], 2)


if __name__ == '__main__':
    unittest.main()
