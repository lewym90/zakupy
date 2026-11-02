# Zbieracz ofert (serwer)

Dwa razy dziennie pobiera oferty sieci i zapisuje jedno `oferty.json`, które aplikacja Zakupy czyta z Twojego serwera.

- **Kaufland** – kafelki ze strony ofert, bez AI (cena, cena jednostkowa, ważność sprawdzane kodem).
- **Lidl** – strony gazetki odczytuje Gemini, kod weryfikuje; niepewne pozycje dostają znacznik `check`.
- **Biedronka** – jeszcze nie.

Uruchomienie ręczne: `systemctl start zakupy-zbieracz`, logi: `journalctl -u zakupy-zbieracz -f`.
Klucz Gemini: plik `/etc/zakupy-zbieracz.env` (pole `GEMINI_API_KEY=`). Bez klucza zbierany jest tylko Kaufland.
Testy: `python3 -m unittest test.test_normalize test.test_zrodla` (z katalogu `server`).
Dane są tylko dla właściciela (adres z tajnym tokenem); nie wrzucaj `oferty.json` do publicznego repozytorium.
