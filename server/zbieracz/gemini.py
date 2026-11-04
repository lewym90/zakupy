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
        self.tried = {self.model}

    def _next_model(self):
        """Inny model flash/flash-lite z własnym dziennym limitem (darmowe limity są liczone osobno dla każdego modelu)."""
        cand = []
        try:
            models = _req(f'{BASE}/models?pageSize=200', self.key).get('models', [])
        except GeminiError:
            return None
        for m in models:
            name = re.sub(r'^models/', '', str(m.get('name', '')))
            mm = re.fullmatch(r'gemini-(\d+(?:\.\d+)?)-flash(-lite)?', name)
            if mm and 'generateContent' in m.get('supportedGenerationMethods', ['generateContent']) and name not in self.tried:
                cand.append((-float(mm.group(1)), bool(mm.group(2)), name))
        return sorted(cand)[0][2] if cand else None

    def _call(self, image_bytes, prompt):
        url = f'{BASE}/models/{self.model}:generateContent'
        imgs = image_bytes if isinstance(image_bytes, (list, tuple)) else [image_bytes]
        mime = lambda b: 'image/webp' if b[:4] == b'RIFF' else 'image/png' if b[:4] == b'\x89PNG' else 'image/jpeg'
        parts = [{'text': prompt}] + [{'inline_data': {'mime_type': mime(b), 'data': base64.b64encode(b).decode()}} for b in imgs]
        body = {'contents': [{'parts': parts}],
                'generationConfig': {'responseMimeType': 'application/json', 'temperature': 0}}
        return _req(url, self.key, body)

    def read_json(self, image_bytes, prompt):
        wait = self.pause - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        attempt = -1
        while attempt < 3:  # zmiana modelu nie zużywa prób, a modeli jest skończona liczba (self.tried)
            attempt += 1
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
                res = json.loads(txt)
                if not isinstance(res, dict):  # np. dosłowne "null": to pusta odpowiedź, nie wynik
                    raise ValueError('odpowiedź nie jest obiektem JSON: ' + txt[:200])
                return res
            except GeminiError as e:
                if e.status == 429 and re.search(r'PerDay|per day|daily', str(e), re.I):
                    nxt = self._next_model()
                    if nxt:
                        print(f'Gemini: dzienny limit modelu {self.model}; przechodzę na {nxt}. ({str(e)[:300]})', flush=True)
                        self.model = nxt; self.tried.add(nxt); attempt -= 1
                        continue
                    raise DailyQuota(e.status, str(e))  # nie ma już modelu z wolnym limitem
                if e.status == 503 and attempt >= 1:  # model przeciążony: inny model zamiast czekania
                    nxt = self._next_model()
                    if nxt:
                        print(f'Gemini: model {self.model} przeciążony; przechodzę na {nxt}.', flush=True)
                        self.model = nxt; self.tried.add(nxt); attempt -= 1
                        continue
                if e.status in (0, 429, 500, 503) and attempt < 3:
                    time.sleep(65 if e.status == 429 else 25 * (attempt + 1))
                    continue
                raise
            except (KeyError, IndexError, ValueError) as e:
                if attempt < 1:
                    continue
                raise GeminiError(0, f'Odpowiedź modelu {self.model} nie jest poprawnym JSON-em: {str(e)[:220]}')
        raise GeminiError(0, 'Gemini nie dało odpowiedzi mimo ponawiania.')
