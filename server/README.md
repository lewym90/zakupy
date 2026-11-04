# Zbieracz ofert (serwer)

Dwa razy dziennie pobiera oferty sieci i zapisuje jedno `oferty.json`, które aplikacja Zakupy czyta z Twojego serwera.

- **Kaufland** – kafelki ze strony ofert, bez AI (cena, cena jednostkowa, ważność sprawdzane kodem).
- **Lidl** – Gemini tylko przepisuje tekst ze stron gazetki; liczby liczy kod i sprawdza je z wydrukowaną ceną jednostkową. Niepotwierdzone pozycje dostają znacznik `check` i aplikacja nie pokazuje dla nich przeliczeń.
- **Biedronka** – gazetki spożywcze z publicznego leaflet-api; odczyt jak w Lidlu. Koniec ważności: z tekstu strony albo 6 dni po dacie z adresu.

Uruchomienie ręczne: `systemctl start zakupy-zbieracz`, logi: `journalctl -u zakupy-zbieracz -f`.
Klucz Gemini: plik `/etc/zakupy-zbieracz.env` (pole `GEMINI_API_KEY=`). Bez klucza zbierany jest tylko Kaufland.
Testy: `python3 -m unittest test.test_zlote test.test_normalize test.test_zrodla` (z katalogu `server`).
Dane są tylko dla właściciela (adres z tajnym tokenem); nie wrzucaj `oferty.json` do publicznego repozytorium.
