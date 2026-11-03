# KONTYNUACJA: Zakupy (prywatna aplikacja PWA do cen, ofert i budżetu)

> Ten plik ma pozwolić nowemu Claude (na nowym koncie) przejąć pracę bez utraty kontekstu. Jest w PUBLICZNYM repozytorium, więc nie ma w nim żadnych kluczy, tokenów ani adresów prywatnego serwera. Stan na 2026-11-02, wersja aplikacji 0.6.1.

## 0. Co zrobić jako pierwsze (nowy Claude)
1. Przeczytaj cały ten plik, potem `README.md` i `server/README.md`. Nie zaczynaj od zera i nie przepisuj działających rzeczy bez powodu.
2. Uruchom testy i potwierdź, że repo jest spójne: `node test/unit.mjs`; `python3 test/e2e.py` (Playwright + Chromium); `python3 test/e2e_gemini.py` (wymaga `/tmp/receipt.jpg` z `python3 mkreceipt.py`, jeśli skryptu brak, pomiń); w katalogu `server`: `python3 -m unittest test.test_zlote test.test_normalize test.test_zrodla`. Wersja w `js/app.js` (VERSION) musi równać się wersji w `sw.js` (VER).
3. **Najpilniejsze zadanie: dokończyć weryfikację sekcji 5 na serwerze (sekcja 8, punkt 2).** Przebudowa z v0.4.0 jest w kodzie i przechodzi testy na tekstach z gazetki, ale nie była jeszcze sprawdzona na prawdziwym odczycie Gemini.
4. Rozmawiaj po polsku, krótko, konkretnie. Patrz sekcja 1.

## 1. Właściciel i zasady współpracy (obowiązują zawsze)
- Polak z Lublina, osoba nietechniczna, buduje aplikacje dla siebie, rodziny i znajomych (niekomercyjnie). Ma też inne aplikacje na tym samym serwerze: to inne projekty, nie ruszaj ich.
- Serwer obsługuje przez Termius (SSH, użytkownik root, host `lewym90`). **Jedna komenda naraz**, gotowa do wklejenia, z jasnym opisem kroku po kroku. Nie każ mu nic wymyślać ani czytać długich instrukcji.
- **Klucze, hasła i tokeny nigdy w czacie ani w repo.** Klucz Gemini właściciel wpisuje sam: w aplikacji (Ustawienia) i w pliku `/etc/zakupy-zbieracz.env` na serwerze (`GEMINI_API_KEY=`). Token adresu ofert jest tylko na serwerze w tym samym pliku.
- Właściciel jest zniecierpliwiony, gdy Claude „pajacuje”, zgaduje albo wciska nieprzetestowane rzeczy. Mów wprost, co działa, a co nie. Nie deklaruj, że coś działa, jeśli nie sprawdziłeś na prawdziwych danych.
- Instalator wypisuje na końcu token adresu ofert: nigdy nie proś o wklejenie tej linii (nie używaj `| tail -1`), kieruj wynik instalatora do `>/dev/null`.
- Testuj sam (Playwright w piaskownicy), zanim cokolwiek wyślesz. Piaskownica Claude NIE ma dostępu do stron sieci handlowych; testy źródeł idą na atrapach, realne sprawdzenie robi serwer właściciela (poproś o log: `journalctl -u zakupy-zbieracz -n 30 --no-pager | cut -c1-170`).
- Repo jest publiczne: bez skopiowanych danych ofert sieci, bez sekretów. Oferty trafiają na prywatny serwer pod tajnym adresem i do telefonu.
- Wygląd ma być bardzo ładny, schludny i czytelny na telefonie, tablecie i laptopie.
- Zasady sieci: bez omijania zabezpieczeń anty-botowych/CAPTCHA; bez automatycznego logowania do kont (Lidl Plus, Kaufland Card); tylko dane (produkt, cena, ważność, sklep), nie kopiujemy zdjęć i grafik z gazetek.

## 2. Cel produktu
Osobiste centrum zakupów: własny cennik z paragonów (zdjęcie paragonu czytane przez Gemini, kod weryfikuje sumy), budżet, oferty sieci (Kaufland, Lidl, Biedronka), ocena promocji względem własnych cen, **porównanie ofert między sieciami** (najważniejsze są promocje wielosztukowe), plan miesiąca, spiżarnia, trasy, alerty. Gemini ma tylko „czytać”; liczy i weryfikuje KOD. Brak danych = brak oceny, nigdy zgadywanie cen.

## 3. Wymagania właściciela dotyczące wyświetlania ofert (dosłowne ustalenia)
Dotyczy listy ofert, szczegółów i **porównania** (wszędzie ten sam układ):
1. **Cena opakowania** (to jest „sztuka”: jedno opakowanie papieru toaletowego, jedna paczka żelków, jedna paczka kawy 1 kg, itd.) jako główna liczba.
2. Pod spodem **zawartość opakowania**: „1 kg”, „300 g”, „8 rolek”, „40 arkuszy”, „3 × 1,5 l = 4,5 l”.
3. Pod spodem **przeliczenie**: za 1 kg kawy, za 100 g żelków, za 1 rolkę papieru toaletowego, za 1 litr coli. Reguła: poniżej 1 kg (1000 g) przeliczamy na 100 g, od 1 kg na kilogramy; płyny na litr; rzeczy liczone na sztuki na rolkę/arkusz/kapsułkę/sztukę. W porównaniach jedna wspólna jednostka w całej grupie (100 g, jeśli któraś oferta jest < 1 kg). Wnioski właściciel wyciąga sam („trochę droższe, ale większe, więc taniej za 100 g”).
4. **Promocje wielosztukowe są najważniejsze** (3 za 2, 3 w cenie 2, 2+1 gratis, 3 za X zł, drugi produkt −50% itd.). Muszą być oznaczone **dokładnie jak w sklepie** („3 za 2”, „3 za 9,99 zł”) i mieć informację **gdzie szukać** (np. „gazetka Lidl, str. 14”, dział w Kauflandzie), bo takie promocje bywają w osobnych miejscach, nie na zwykłej półce.
5. Porównanie ma uwzględniać te promocje i liczyć realną cenę za litr/kg/sztukę w komplecie (np. Lidl: 3 butelki coli w promocji kontra Kaufland: 2 butelki).
6. Pod uwagę brać całą ofertę ze stron sieci (nie tylko gazetki), jeśli sieć ją publikuje.

## 4. Architektura i stan techniczny
### Aplikacja (GitHub Pages, frontend)
- Vanilla JS (ES modules), IndexedDB (`receipts`, `offers`, `kv`), service worker: cache-first + odświeżanie w tle, wersjonowany cache, auto-aktualizacja przy każdym uruchomieniu (`reg.update()`, przeładowanie przy `controllerchange`). Pieniądze w groszach.
- `js/app.js` (UI, ekrany: Start, Paragony, Cennik, Okazje, Budżet, Ustawienia), `js/offers.js` (obliczenia ofert: `offerCalc`, `compareGroups`, `packLabel`, `unitPrice`, `promoLabel`, `whereLabel`, `isMulti`, rodziny produktów `FAMILIES`), `js/gemini.js` (odczyt paragonów: model `gemini-3.8-flash`, fallback przez ListModels), `js/calc.js`, `js/cats.js`, `js/db.js`, `js/util.js`, `sw.js`, `css/app.css`.
- Model oferty: `{id, store, name, price (grosze, całego opakowania lub kompletu), old, amount (w JEDNYM opakowaniu), unit szt|kg|g|l|ml, mode unit|bundle|nth, need, pay, pct, from, until, cond, section, page, src, conf ok|check, note, promo}`. W trybie `bundle` `price` to cena całego kompletu `need` sztuk; `pay` = za ile sztuk płacisz (3 za 2). `nth`: kup `need`, ostatnia o `pct`% taniej.
- Oferty z serwera są tylko do odczytu (id `s:…`), znacznik „odczyt do sprawdzenia” przy `conf:'check'`. Adres ofert wpisuje się w Ustawieniach.
- Układ responsywny: <720 px dolny pasek, ≥720 pasek ikon, ≥1100 szeroki pasek i siatki.

### Zbieracz ofert (serwer właściciela, katalog `server/`)
- Python + Playwright (Chromium) w venv, użytkownik systemowy `zakupy`, kod w `/opt/zakupy-zbieracz`, stan w `/var/lib/zakupy-zbieracz` (cache odczytów Lidla, archiwum dzienne), wynik `/var/www/zakupy-data/oferty.json` serwowany przez Caddy pod ścieżką z tajnym tokenem (`/zakupy-oferty/<TOKEN>/oferty.json`, CORS `*`). Timer systemd dwa razy dziennie (05:20 i 17:40).
- Instalacja/aktualizacja (idempotentna, zachowuje klucz i token): `curl -fsSL https://raw.githubusercontent.com/lewym90/zakupy/main/server/deploy/install.sh | bash`. Ręczny odczyt: `systemctl start zakupy-zbieracz`. Plik ustawień: `/etc/zakupy-zbieracz.env` (`GEMINI_API_KEY`, `TOKEN`, opcjonalnie `ZBIERACZ_GEMINI_MODEL`, `ZBIERACZ_PAUSE` (domyślnie 13 s), `LIDL_BATCH` (domyślnie 3 strony na zapytanie), `LIDL_MAX_PAGES`).
- `zbieracz/kaufland.py`: kafelki ze strony ofert (HTML, **bez AI**, zweryfikowane na prawdziwej stronie: ok. 900 ofert, strona przeszła przez Cloudflare z serwera). `zbieracz/lidl.py`: gazetka Lidla z publicznego JSON platformy gazetek, strony-obrazy czytane przez Gemini. `zbieracz/normalize.py`: parsowanie opakowań, cen jednostkowych, ważności, `parse_multibuy`, `apply_multibuy`, `verify`, `verify_any`. `zbieracz/gemini.py`: klient z ponawianiem (429/503/timeout), zmianą modelu po dziennym limicie, odczyt wielu obrazów w jednym zapytaniu. `zbieracz/run.py`: orkiestracja i zapis `oferty.json` (format `{v:1, updated, stores, offers[]}`).
- Darmowy klucz Gemini ma **dzienny limit zapytań liczony osobno dla każdego modelu**; odczyt całej gazetki Lidla (ok. 110 stron) wymaga zbijania stron w paczki i cache (zrobione, cache kluczowany wersją promptu `|v2`).
- Wersje (git): v0.1.0 → v0.3.2 (afa54f0); zbieracz w `34e6ba6` i dalej.

## 5. KRYTYCZNY PROBLEM: odczyt Lidla przez Gemini daje błędne dane
Właściciel wstawił zrzuty ekranu strony 10–11 gazetki Lidl (`lidl.pl/l/pl/gazetki/gazetka-02-11-pon-kw45/view/flyer/page/10`) i porównał z aplikacją.
- Gazetka: „Coca-Cola, Coca-Cola Zero, Fanta lub Sprite, **Dwusztuk, 2 x 1 L**, 1 L = 4,99 + kaucja 1,00 zł, **2 x 4,99 zł za butelkę, 9,98**”. Aplikacja pokazała: „2 za 9,98 zł”, „2 × 2 l = 4 l”, **2,50 zł za litr** (powinno być 2 × 1 l = 2 l, **4,99 zł za litr**).
- Gazetka: „Coca-Cola lub Coca-Cola Zero, **Czterosztuk, 4 x 2 L**, 1 L = 4,00 + kaucja 2,00 zł, **4 x 7,99 zł za butelkę, 31,96**”. Aplikacja pokazała: „4 za 31,96 zł”, „4 × 8 l = 32 l”, **1,00 zł za litr** (powinno być 4 × 2 l = 8 l, **4,00 zł za litr**).
- Ta sama strona ma ofertę „**2 + 1 gratis**, aktywuj kupon w aplikacji Lidl Plus, miksuj dowolnie” (Pepsi Zero, Mirinda, 7UP, Pepsi/Pepsi Twist 2 L, cena poza promocją 10,15 zł/but., 1 L = 5,08 + kaucja 0,50 zł, limit 1 but. gratis na kupon) oraz „Sześciosztuk 6 x 1,5 L, 6 x 1,79 zł za butelkę, 10,74, 1 L = 1,19 + kaucja 3,00 zł” (Żywiec Zdrój).
- **Przyczyna:** model wpisał do pola `opakowanie` tekst już zawierający mnożnik („2 x 1 L”, „4 x 2 L”), a kod pomnożył jeszcze raz przez `komplet_ilosc`, czyli policzył liczbę sztuk podwójnie. Kontrola `verify_any` porównuje cenę jednej sztuki z ceną jednostkową ze strony, więc taka oferta dostała `conf:'check'` („odczyt do sprawdzenia”), ale **aplikacja mimo to pokazała błędną cenę za litr**, co jest niedopuszczalne. Dodatkowo kaucja (osobna, nieliczona w cenie jednostkowej) bywa mylona z ceną.
- Wniosek właściciela (dosłownie w sensie): nie można ufać Gemini; „to wszystko musi być przebudowane od nowa”. Gemini sprawdza się tylko jako czytnik tekstu, nie jako źródło liczb.

**Stan po v0.4.0:** przyczyna usunięta w kodzie. Gemini tylko przepisuje tekst (nowy prompt, klucz cache `|v3`), a `normalize.interpret` układa możliwe odczytania i przyjmuje tylko takie, które zgadza się z wydrukowaną ceną jednostkową (±2%, kaucja osobno). Bez tej ceny wystarcza zgodny druk „N x cena = suma kompletu”. W innym wypadku oferta dostaje `conf:'check'`: bez przeliczeń, poza porównaniem, ukryta za paskiem „Ukryto N ofert” z przyciskiem „Pokaż”. Złote testy: `server/test/test_zlote.py`. Od v0.4.1 jest trzeci stan `conf:'cena'` (Kaufland, dane bez AI): cena pewna, ale bez ceny za jednostkę (kilka wariantów, brak ilości). Taka oferta jest widoczna, tylko bez przeliczeń, oceny i porównania. Niezweryfikowane: prawdziwy odczyt nowego promptu przez Gemini.

## 6. Plan przebudowy (zalecany; uzgodnij z właścicielem)
Wykonane w v0.4.0: punkty 1-5, 7, 8 (link do strony gazetki w szczegółach oferty, bez miniatury), 9 (nowy klucz cache). Otwarte: punkt 6.

1. **Zasada nadrzędna:** niezweryfikowana liczba nie może trafić do widoku jako pewna. Oferta z `conf:'check'` NIE pokazuje obliczonej ceny za litr/kg (pokazuje cenę opakowania i napis „odczyt niepewny”), jest poza „najtaniej” i poza sortowaniem porównań; domyślnie ukryta za przełącznikiem „pokaż niepewne”.
2. **Gemini jako OCR, nie interpretacja:** poproś model tylko o dosłowny odczyt tekstu z bloków oferty (nazwa, tekst opakowania, napis promocji, cena, tekst „1 L = …”, kaucja), zero wnioskowania. Całą semantykę (liczba sztuk, objętość sztuki, promocja, cena komplet/jednostka) liczy deterministyczny kod z `normalize.py` (`parse_pack`, `parse_multibuy`).
3. **Kotwica: cena jednostkowa wydrukowana w gazetce.** Z ceny kompletu i wydrukowanego „1 L = X” wylicz implikowaną ilość i wybierz tę interpretację zawartości (np. 8 l, nie 32 l), która zgadza się z nią (±2%, z uwzględnieniem, że kaucja jest dopisana osobno i nie wchodzi do ceny). Brak zgodności = `check`, bez liczb pochodnych.
4. **Brak podwójnego liczenia:** jeśli tekst opakowania zawiera mnożnik („Dwusztuk 2 x 1 L”, „Czterosztuk 4 x 2 L”, „6 x 1,5 L”), to ilość całego kompletu jest już w tekście; nie mnóż drugi raz przez `komplet_ilosc`. Dodaj do testów te dokładne przypadki (dane powyżej).
5. Dodać do testów zestaw „złotych” przypadków z prawdziwych stron gazetek (tekst ze zrzutów) i wymagać dokładnych wyników (4,99 zł/l, 4,00 zł/l, 1,19 zł/l).
6. Rozważyć lepsze, nie-AI źródła strukturalne: Kaufland (HTML, już działa), strony produktowe/ofertowe Lidla (lidl.pl), dane Biedronki; gazetka tylko jako uzupełnienie. Zbadać, czy JSON platformy gazetek (`endpoints.leaflets.schwarz/v4/flyer?...`) ma strukturalne pola produktów na stronach (wcześniej: zaszumiony tekst `keyWords`, tylko kilka produktów strukturalnych).
7. Dla „gdzie szukać” dodać link do strony gazetki: `https://www.lidl.pl/l/pl/gazetki/<slug>/view/flyer/page/<N>` (wiemy, że ten adres działa w przeglądarce).
8. Dodać w aplikacji widok kontroli: obok oferty miniatura/link do strony gazetki, żeby właściciel mógł zweryfikować.
9. Po przebudowie: wyczyścić cache Lidla (zmień wersję klucza cache, np. `|v3`) i przeczytać gazetkę od nowa. Pamiętaj o dziennych limitach darmowego klucza Gemini.

## 7. Co działa, a co nie jest zweryfikowane
Działa i przetestowane: aplikacja (Start, Paragony, Cennik, Budżet, Okazje, Ustawienia), układ responsywny, autoaktualizacja, adres ofert i pobieranie, układ ofert (cena opakowania, zawartość, przeliczenie), oznaczenia promocji i filtr „Komplety i 2+1”, Kaufland (ok. 900 ofert z prawdziwej strony), zbieracz (instalator, timer, Caddy, ponawianie, fallback modelu).
Do potwierdzenia na serwerze: **odczyt Lidla po przebudowie (sekcja 5)**. Kaufland: promocja jest pewna tylko wtedy, gdy stoi w etykiecie ceny i cena zgadza się z ceną za jednostkę; wykryta jedynie w opisie kafelka zostaje niepewna (brak prawdziwych próbek).
Niezweryfikowane: odczyt zdjęcia paragonu przez Gemini na żywo i przycisk „Sprawdź klucz”; iPhone/Safari (ekran początkowy, aparat, autoaktualizacja w trybie standalone); prawdziwy tablet/laptop; nazwa modelu `gemini-3.8-flash` (z komunikatu Google).
Biedronka: brak źródła; gazetki to płótno createjs z obrazami, trzeba zbadać viewer i adresy obrazów stron (przeglądarka w sesji dała dostęp do stron sklepów).

## 8. Zadania w kolejności
Dodane w v0.6.0: nowa szata graficzna „etykieta cenowa” (czcionka Onest w `fonts/`, licencja OFL; ikony w `js/icons.js` zamiast emoji; cena przez funkcję `pr()`; jedyny mocny akcent to żółta metka `--tag`, nie dodawać kolorów). Nawigacja: na telefonie pięć zakładek (Start, Okazje, Lista, Paragony, Więcej), na większym ekranie wszystko w pasku bocznym. Funkcje w `js/plan.js`: najtańszy koszyk i stałe produkty (w Liście), spiżarnia, plan miesiąca (w Budżecie). Do koszyka i alertów trafiają tylko oferty z potwierdzoną ceną za jednostkę. Alerty są tylko w aplikacji, na ekranie Start, bez powiadomień push.
Dodane w v0.5.0: zakładka Lista (`js/lista.js`, dane w kv `lista`): „+” przy ofercie, grupy po sklepach, filtr sklepu, odhaczanie, liczba sztuk, pozycje ręczne. Kategorie: `catOf` patrzy najpierw na słowa przed „z/do/o...”, a właściciel może poprawić kategorię w szczegółach oferty (kv `catFix`, wygrywa z automatem). Do zrobienia: mapowanie działów Kauflandu (`section`) na kategorie.
1. ZROBIONE w v0.4.0: przebudowa odczytu ofert i widoku niepewnych ofert.
2. Weryfikacja na serwerze: właściciel uruchamia aktualizację i odczyt; Claude analizuje log i `oferty.json` na przykładach (poproś o fragmenty).
3. Biedronka.
4. Poprawa dopasowania „rodzin” produktów w porównaniu (słownik `FAMILIES` jest prosty; cola łączy marki; nie zna smaków i wariantów).
5. Znajomy (inny projekt właściciela) i typer-ai używają prawdopodobnie wycofanego modelu `gemini-2.5-flash`; przypomnij właścicielowi o sprawdzeniu `ZNAJOMY_GEMINI_MODEL`/konfiguracji (to osobne projekty).
6. Dalej: plan miesiąca, spiżarnia, trasy, synchronizacja dla partnerki, alerty push, analizy (inflacja osobista, cena za 100 g białka, shrinkflation), ikony kategorii, e-paragony.

## 9. Wyniki badania źródeł (przeglądarka, 2026-11-02)
- **Kaufland:** `https://sklep.kaufland.pl/oferta/przeglad.html?kloffer-week=current` (też `next`). Kafelki `.k-product-tile` z polami `__title`, `__subtitle`, `__unit-price`, `__base-price`, `.k-price-tag__discount/__price/__old-price-line-through`; sekcje i ważność („Oferta ważna od … do …”) w tekście przed kafelkami.
- **Lidl:** spożywcze promocje tylko w gazetce (`lidl.pl/l/pl/gazetki/<slug>/ar/0`, podgląd `.../view/flyer/page/<N>`), ok. 110 stron głównej gazetki; JSON `https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier=<slug>&region_id=0&region_code=0` (daty, strony-obrazy). Gazetki-katalogi (nie jedzenie) są pomijane.
- **Biedronka:** gazetki jako płótno createjs; do zbadania.
- Z piaskownicy Claude żadna z tych domen nie jest osiągalna; realne testy tylko przez serwer właściciela.

## 10. Rozmowa w skrócie (historia decyzji)
1. Właściciel chciał prywatnej aplikacji PWA „Zakupy” na iPhone: cennik z paragonów (zdjęcie → Gemini), budżet, gazetki, ocena promocji względem własnych cen.
2. Dodano zakładkę Ustawienia (wersja, ręczne odświeżanie, auto-aktualizacja przy starcie, klucz Gemini).
3. Prośba o analizę nie tylko gazetek, ale całej oferty sieci, oraz porównywarkę (np. 3 butelki coli w Lidlu kontra 2 w Kauflandzie, na litr/butelkę); przeskalowanie aplikacji na telefon, tablet i laptop.
4. Google wycofał `gemini-2.5-flash` (błąd 404): model domyślny `gemini-3.8-flash` plus automatyczny wybór działającego modelu.
5. Zgoda na zbieracz na serwerze („masz zgodę”): powstał `server/`, wdrożony; Kaufland działa; Lidl wymagał obejścia limitów darmowego klucza (paczki po 3 strony, tempo 13 s, zmiana modelu po dziennym limicie, ponawianie).
6. Właściciel poprawił sposób wyświetlania ofert (sekcja 3): cena opakowania, zawartość, przeliczenie; potem żądał uwzględnienia promocji wielosztukowych jak w sklepie i miejsca w gazetce.
7. Na koniec właściciel wykazał błędne odczyty Lidla (sekcja 5) i zdecydował, że odczyt trzeba przebudować, oraz poprosił o zapis całego kontekstu do tego pliku, żeby kontynuować pracę na nowym koncie.
