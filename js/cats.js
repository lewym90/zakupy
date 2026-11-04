// Kategorie i deterministyczne dopasowanie po słowach kluczowych (bez AI).
// Klucz kończący się na $ = dokładne słowo; pozostałe = początek słowa; z odstępem = początek frazy.
// O kategorii decyduje to, CZYM jest produkt: pierwsze rozpoznane słowo nazwy przed „z”, „do”, „o”...
// Dopiero gdy tam nic nie ma, liczą się dalsze słowa (Filet z dorsza). „Karma z kurczakiem” to karma, nie mięso.
import { norm } from './util.js';

export const CATS = [
  { id: 'ryby', n: 'Ryby', k: ['losos', 'dorsz', 'ryba', 'ryby', 'sledz', 'tunczyk', 'makrel', 'pstrag', 'karp', 'mintaj', 'krewetk', 'sushi'] },
  { id: 'wedliny', n: 'Wędliny', k: ['kielbas', 'szynk', 'parowk', 'kabanos', 'prosciutto', 'pancetta', 'spianata', 'wedlin', 'salami', 'pasztet', 'kaszank', 'mortadel', 'boczek', 'polędwica sopocka', 'baleron'] },
  { id: 'mieso', n: 'Mięso i drób', k: ['karkow', 'schab', 'kurczak', 'kurcz', 'mielon', 'wieprz', 'wolow', 'indyk', 'udko', 'udka', 'skrzyd', 'poledwic', 'zeberk', 'lopatk', 'antrykot', 'golonk', 'mieso', 'kaczk', 'cielec', 'pulpet', 'kotlet', 'rostbef', 'zraz', 'piers$'] },
  { id: 'nabial', n: 'Nabiał i jaja', k: ['mleko', 'ser$', 'serek', 'serki', 'jogurt', 'maslo', 'smietan', 'twarog', 'kefir', 'jaja', 'jajka', 'maslank', 'margaryn', 'mozzarell', 'feta', 'skyr', 'serwatk', 'deser mlecz', 'budyn'] },
  { id: 'warzywa', n: 'Warzywa i owoce', k: ['ziemniak', 'marchew', 'cebul', 'pomidor', 'ogorek', 'ogorki', 'jablk', 'banan', 'salat', 'papryk', 'cytryn', 'pomarancz', 'mandar', 'winogron', 'truskaw', 'brokul', 'kapust', 'por$', 'czosnek', 'burak', 'szpinak', 'grzyb', 'pieczark', 'awokado', 'kaki$', 'gruszk', 'kiwi', 'warzyw', 'owoc', 'borowk', 'maliny', 'cukini', 'dynia', 'rzodkiew', 'seler', 'pietruszk', 'koperek'] },
  { id: 'pieczywo', n: 'Pieczywo', k: ['chleb', 'bulk', 'bagiet', 'drozdzowk', 'rogal', 'precel', 'tost', 'pieczyw', 'chalk', 'pączek', 'paczek', 'bulka'] },
  { id: 'mrozonki', n: 'Mrożonki i lody', k: ['mrozon', 'lody', 'lod$', 'pizza', 'frytki', 'pierogi', 'paluszki rybne', 'nuggets'] },
  { id: 'napoje', n: 'Napoje', k: ['woda', 'wody', 'sok$', 'soki$', 'cola', 'pepsi', 'napoj', 'lemoniad', 'nektar', 'izotonik', 'energet', 'oranzad', 'fanta', 'sprite', 'tonik', 'mleko ryzowe', 'kompot'] },
  { id: 'kawa', n: 'Kawa i herbata', k: ['kawa$', 'kawy$', 'kawe$', 'herbata$', 'herbaty$', 'herbatka$', 'herbatki$', 'kakao', 'nescafe', 'cappuccino', 'espresso', 'lavazza', 'tchibo', 'jacobs', 'melitta', 'ziarnist'] },
  { id: 'alkohol', n: 'Alkohol', k: ['piwo', 'kasztelan', 'jasne pelne', 'niepasteryzowane', 'perla', 'carlsberg', 'heineken', 'desperados', 'lomza', 'radler', 'pilsner', 'lager', 'tyskie', 'okocim', 'warka', 'lech$', 'kozel', 'harnas', 'zywiec jasne', 'zywiec biale', 'wino', 'wodka', 'whisky', 'rum$', 'gin$', 'likier', 'cydr', 'prosecco', 'szampan', 'nalewk', 'koniak', 'brandy'] },
  { id: 'slodycze', n: 'Słodycze i przekąski', k: ['czekolad', 'baton', 'chips', 'ciastk', 'paluszk', 'cukierk', 'wafel', 'wafle', 'zelk', 'orzeszk', 'chrupki', 'lizak', 'delicj', 'pralin', 'snickers', 'prince polo', 'krakers', 'popcorn', 'ciasto', 'sernik', 'orzech', 'migdal', 'rodzynk', 'zurawin', 'daktyl', 'nerkow', 'pistacj', 'bakali', 'herbatnik', 'pierni', 'mieszanka studencka', 'suszone sliwk', 'sliwki suszone'] },
  { id: 'spizarnia', n: 'Spiżarnia', k: ['makaron', 'ryz$', 'maka$', 'mak$', 'cukier', 'olej', 'oliwa', 'kasza', 'platki', 'sol$', 'przypraw', 'ocet', 'keczup', 'majonez', 'musztard', 'konserw', 'fasol', 'groch', 'dzem', 'miod', 'sos$', 'sosy$', 'zupa', 'buljon', 'kukurydz', 'ciecierzyc', 'soczewic', 'musli', 'przecier', 'koncentrat', 'drozdze', 'proszek do pieczenia', 'galaretk', 'tortilla', 'ryzowe', 'pestk', 'sezam', 'siemie', 'danie gotowe', 'mieszanka do wypiek'] },
  { id: 'chemia', n: 'Chemia i higiena', k: ['plyn', 'proszek', 'papier', 'mydl', 'szampon', 'pasta do zeb', 'zel pod', 'recznik', 'chusteczk', 'worki', 'gabka', 'kapsulk', 'odplamiacz', 'dezodorant', 'higien', 'podpask', 'pieluch', 'tabletk', 'plyn do', 'folia', 'torebki', 'ręcznik', 'szczoteczk', 'krem$', 'balsam', 'odzywk', 'wacik', 'patyczk', 'baterie', 'zarowk', 'swiec', 'golen', 'maszynk', 'wklady$', 'farba', 'odswiezacz', 'mleczko', 'perfum', 'pomadk', 'tampon', 'antyperspirant', 'zel$', 'plukank', 'czyszcz', 'spray'] },
  { id: 'zwierzeta', n: 'Dla zwierząt', k: ['karma', 'zwirek', 'whiskas', 'pedigree', 'kocie', 'psie', 'sheba', 'felix'] },
  { id: 'inne', n: 'Inne', k: [] },
];

const byId = Object.fromEntries(CATS.map(c => [c.id, c]));
export const catById = id => byId[id] || byId.inne;

// Kolejność dopasowania (od najbardziej szczegółowych): np. "kawa mielona" ma trafić do kawy, nie do mięsa.
const ORDER = ['kawa', 'napoje', 'alkohol', 'ryby', 'wedliny', 'mieso', 'nabial', 'mrozonki', 'pieczywo', 'warzywa', 'slodycze', 'spizarnia', 'chemia', 'zwierzeta', 'inne'];
const prepared = [...CATS].sort((a, b) => ORDER.indexOf(a.id) - ORDER.indexOf(b.id))
  .map(c => ({ id: c.id, k: c.k.map(k => (k.endsWith('$') ? norm(k) + '$' : norm(k))).filter(Boolean) }));

// Wyjątki sprawdzane przed wszystkim innym.
const PHRASES = [['platki hydrozel', 'chemia'], ['platki pod oczy', 'chemia'], ['maska do wlosow', 'chemia'], ['mieszanka chinsk', 'mrozonki'], ['mieszanka meksyk', 'mrozonki'], ['napoj jogurt', 'nabial'], ['mieszanka krolewska', 'slodycze'], ['woda micelarna', 'chemia'], ['woda toaletowa', 'chemia'], ['woda perfumowana', 'chemia'], ['krem do', 'chemia'], ['maslo orzech', 'spizarnia'], ['maslo shea', 'chemia'],
  ['mleko kokosowe', 'spizarnia'], ['mleko do ciala', 'chemia'], ['rolada ogrodowa', 'slodycze'], ['rolada biszkopt', 'slodycze'], ['paluszki rybne', 'mrozonki'], ['paluszki krabowe', 'ryby']];
const MODIFIERS = new Set(['z', 'ze', 'o', 'w', 'we', 'do', 'na', 'dla', 'bez', 'od', 'po']);
const GENERIC_MEAT = new Set(['filet', 'filety', 'fileciki', 'rolada', 'rolady']); // samo w sobie nic nie mówi: Filet z dorsza to ryba

function matchAt(toks, i) {
  const t = toks[i], rest = toks.slice(i).join(' ');
  for (const [k, id] of PHRASES) if (rest.startsWith(k)) return id;
  for (const c of prepared) {
    for (const k of c.k) {
      if (k.endsWith('$') ? t === k.slice(0, -1) : k.includes(' ') ? rest.startsWith(k) : t.startsWith(k)) return c.id;
    }
  }
  return null;
}

export function catOf(name) {
  const n = norm(name);
  if (!n) return 'inne';
  const toks = n.split(' ');
  const cut = toks.findIndex((t, i) => i > 0 && MODIFIERS.has(t));
  const head = cut < 0 ? toks.length : cut;
  for (let i = 0; i < toks.length; i++) { // najpierw część przed „z/do/o”, potem reszta, po kolei
    if (i === head) break;
    const id = matchAt(toks, i); if (id) return id;
  }
  for (let i = head; i < toks.length; i++) { const id = matchAt(toks, i); if (id) return id; }
  return toks.some(t => GENERIC_MEAT.has(t)) ? 'mieso' : 'inne';
}

// Działy Kauflandu: sklep sam dzieli oferty, więc to pewniejsze niż nazwa. [kategoria domyślna, inne dozwolone w tym dziale].
// Działy promocyjne (Hity tygodnia, Mocny Start...) nic nie mówią o produkcie, więc tam decyduje nazwa.
const SECTIONS = {
  'Napoje': ['napoje', 'alkohol'], 'Nabiał': ['nabial'], 'Świeże ryby': ['ryby'], 'Mrożonki': ['mrozonki'],
  'Drogeria i Chemia gospodarcza': ['chemia', 'zwierzeta'], 'Kosmetyki, Chemia': ['chemia'],
  'Mięso, Drób, Wędliny': ['mieso', 'wedliny'], 'Kawa, Herbata, Słodycze, Przekąski': ['slodycze', 'kawa'],
  'Garmażeria, Konserwy': ['spizarnia', 'ryby', 'mieso', 'wedliny', 'warzywa'],
  'ABC każdej kuchni': ['spizarnia', 'slodycze', 'kawa', 'warzywa'],
};
export function catOfOffer(name, section) {
  const c = catOf(name), s = SECTIONS[section];
  return !s || s.includes(c) ? c : s[0];
}

export const STORES = ['Biedronka', 'Lidl', 'Kaufland', 'Auchan', 'Carrefour', 'Netto', 'Dino', 'Stokrotka', 'Żabka', 'Inny'];
