"""Gemini jako "oczy": czyta obraz strony gazetki. Wynik to tylko PROPOZYCJA; kod weryfikuje (normalize.verify).
Klucz z /etc/zakupy-zbieracz.env (GEMINI_API_KEY). Adres bazowy można podmienić w testach (GEMINI_BASE)."""
import base64
import json
import os
import re
import time
import urllib.error
import urllib.request

BASE = os.environ.get('GEMINI_BASE', 'https://generativelanguage.googleapis.com/v1beta')
DEFAULT_MODEL = os.environ.get('ZBIERACZ_GEMINI_MODEL', 'gemini-3.8-flash')


class GeminiError(Exception):
    def __init__(self, status, msg):
        super().__init__(msg)
        self.status = status


class DailyQuota(GeminiError):
    pass


def _req(url, key, body=None, timeout=180):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json', 'x-goog-api-key': key})
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read()).get('error', {}).get('message', '')
        except Exception:
            msg = ''
        raise GeminiError(e.code, f'Gemini {e.code}: {msg[:700]}')
    except urllib.error.URLError as e:
        raise GeminiError(0, f'Brak połączenia z Gemini: {e.reason}')
    except (TimeoutError, OSError) as e:  # np. "The read operation timed out"
        raise GeminiError(0, f'Gemini nie odpowiedziało w czasie: {e}')


def pick_flash(models):
    cand = []
    for m in models or []:
        name = re.sub(r'^models/', '', str(m.get('name', '')))
        mm = re.fullmatch(r'gemini-(\d+(?:\.\d+)?)-flash', name)
        if not mm:
            continue
        if 'supportedGenerationMethods' in m and 'generateContent' not in m['supportedGenerationMethods']:
            continue
        cand.append((float(mm.group(1)), name))
    return max(cand)[1] if cand else None


class Reader:
    def __init__(self, key, model=None, pause=None):
        self.key, self.model, self._last = key, model or DEFAULT_MODEL, 0.0
        self.pause = float(os.environ.get('ZBIERACZ_PAUSE', '13')) if pause is None else pause

    def _call(self, image_bytes, prompt):
        url = f'{BASE}/models/{self.model}:generateContent'
        body = {'contents': [{'parts': [{'text': prompt}, {'inline_data': {'mime_type': 'image/jpeg', 'data': base64.b64encode(image_bytes).decode()}}]}],
                'generationConfig': {'responseMimeType': 'application/json', 'temperature': 0}}
        return _req(url, self.key, body)

    def read_json(self, image_bytes, prompt):
        wait = self.pause - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        for attempt in range(4):
            try:
                try:
                    j = self._call(image_bytes, prompt)
                except GeminiError as e:
                    if e.status != 404:
                        raise
                    nxt = pick_flash(_req(f'{BASE}/models?pageSize=200', self.key).get('models'))
                    if not nxt or nxt == self.model:
                        raise GeminiError(404, 'Nie znalazłem działającego modelu Gemini dla tego klucza.')
                    self.model = nxt
                    j = self._call(image_bytes, prompt)
                self._last = time.time()
                txt = ''.join(p.get('text', '') for p in j['candidates'][0]['content']['parts'])
                return json.loads(txt)
            except GeminiError as e:
                if e.status == 429 and re.search(r'PerDay|per day|daily', str(e), re.I):
                    raise DailyQuota(e.status, str(e))  # dzienny limit darmowego klucza: nie ma sensu ponawiać
                if e.status in (0, 429, 500, 503) and attempt < 3:
                    time.sleep(65 if e.status == 429 else 25 * (attempt + 1))
                    continue
                raise
            except (KeyError, IndexError, ValueError):
                if attempt < 1:
                    continue
                raise GeminiError(0, 'Odpowiedź modelu nie jest poprawnym JSON-em.')
