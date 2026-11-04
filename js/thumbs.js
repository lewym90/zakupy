// Zdjęcia produktów: jedna plansza img/produkty.webp (8 × 8 pól). To własne, wygenerowane grafiki, a nie zdjęcia z gazetek.
// Bez planszy (SPRITE = false) produkt pokazuje ikonę kategorii.
import { norm } from './util.js';
export const SPRITE = true;
export const COLS = 8;
// Kolejność pól jest taka sama jak w prompcie do generatora.
export const SLOTS = [
  ['banan', 'banan'], ['jablko', 'jablk'], ['pomidor', 'pomidor'], ['ogorek', 'ogorek|ogorki'], ['ziemniak', 'ziemniak|batat'], ['cebula', 'cebul|czosnek'], ['marchew', 'marchew|burak|pietruszk'], ['papryka', 'papryk'],
  ['cytrus', 'cytryn|pomarancz|mandar|limonk'], ['winogrono', 'winogron|borowk|maliny|truskaw'], ['salata', 'salat|szpinak|kapust|brokul'], ['grzyby', 'pieczark|grzyb'], ['mleko', 'mleko'], ['maslo', 'maslo(?! orzech)|margaryn'], ['ser', 'ser$|gouda|edamski|mozzarell|feta'], ['jajka', 'jaja|jajka'],
  ['jogurt', 'jogurt|skyr|kefir|maslank|deser'], ['smietana', 'smietan|twarog|serek'], ['chleb', 'chleb|tost'], ['bulka', 'bulk|bagiet|rogal|drozdzowk|paczek'], ['drob', 'kurczak|kurcz|indyk|udko|udka|skrzydl|piers'], ['wieprzowina', 'schab|karkow|wieprz|zeberk|lopatk|boczek'], ['wolowina', 'wolow|rostbef|antrykot|mielon'], ['ryba', 'losos|dorsz|ryba|ryby|sledz|tunczyk|makrel|pstrag|mintaj|krewetk'],
  ['szynka', 'szynk|poledwic|baleron|wedlin'], ['kielbasa', 'kielbas|parowk|kabanos|salami'], ['pizza', 'pizza'], ['frytki', 'frytki|pierogi|mrozon|nuggets'], ['lody', 'lody'], ['woda', 'woda(?! micel)|wody'], ['cola', 'cola|pepsi|fanta|sprite|7up|mirinda|napoj|tonik'], ['sok', 'sok|nektar|lemoniad'],
  ['kawa', 'kawa|kawy|nescafe|jacobs|lavazza|tchibo'], ['herbata', 'herbata|herbaty|herbatk'], ['piwo', 'piwo|tyskie|okocim|warka|lech|kozel|zywiec jasne|pilsner|lager'], ['wino', 'wino|prosecco|szampan|wodka|whisky|likier'], ['czekolada', 'czekolad|baton|pralin'], ['ciastka', 'ciastk|herbatnik|pierni|wafel|wafle|ciasto'], ['zelki', 'zelk|cukierk|lizak'], ['chipsy', 'chips|chrupki|paluszk|popcorn|krakers'],
  ['orzechy', 'maslo orzech|orzech|migdal|nerkow|pistacj|rodzynk|bakali|daktyl|zurawin'], ['makaron', 'makaron'], ['ryz', 'ryz|kasza'], ['maka', 'maka|cukier|sol$|platki'], ['olej', 'olej|oliwa'], ['konserwa', 'konserw|fasol|groch|kukurydz|ciecierzyc|soczewic|przecier'], ['sos', 'sos$|sosy|keczup|majonez|musztard|ocet'], ['dzem', 'dzem|miod|krem czekolad'],
  ['zupa', 'zupa|danie gotowe|buljon'], ['przyprawy', 'przypraw|kakao|drozdze|budyn|galaretk'], ['papier', 'papier toaletowy|recznik'], ['proszek', 'proszek|zel do prania|kapsulki do prania|plukank'], ['plyn', 'plyn|czyszcz|spray|odplamiacz'], ['mydlo', 'mydl|zel pod|zel$'], ['szampon', 'szampon|odzywk|farba'], ['krem', 'woda micel|krem|balsam|mleczko|dezodorant|antyperspirant|perfum'],
  ['pasta', 'pasta do zeb|szczoteczk'], ['golenie', 'golen|maszynk|wklady'], ['higiena', 'podpask|tampon|pieluch|chusteczk|wacik|platki kosmetyczne'], ['karma pies', 'karma dla psa|pedigree|psie'], ['karma kot', 'karma|whiskas|sheba|felix|kocie'], ['baterie', 'baterie|zarowk|swiec'], ['worki', 'worki|folia|torebki|gabka|zmywark'], ['produkt', ''],
];
const RX = SLOTS.map(([k, r]) => (r ? new RegExp('(^| )(' + r.replace(/\$/g, '( |$)') + ')') : null));
const CAT_SLOT = { warzywa: 'jablko', pieczywo: 'chleb', nabial: 'mleko', mieso: 'wieprzowina', wedliny: 'szynka', ryby: 'ryba', mrozonki: 'frytki', napoje: 'woda', kawa: 'kawa', alkohol: 'wino', slodycze: 'czekolada', spizarnia: 'makaron', chemia: 'plyn', zwierzeta: 'karma kot' };
export function slotOf(name, cat) {
  // Liczy się to, czym produkt jest: najwcześniejsze słowo, najpierw przed „z”, „o”, „do”. Chipsy o smaku papryki to chipsy.
  const n = norm(name), m = /^(.+?) (z|ze|o|w|we|do|na|dla|bez|po) /.exec(n);
  for (const t of m ? [m[1], n] : [n]) {
    let best = -1, at = Infinity;
    RX.forEach((r, i) => { const x = r && r.exec(t); if (x && x.index < at) { at = x.index; best = i; } });
    if (best >= 0) return best;
  }
  const c = SLOTS.findIndex(s => s[0] === CAT_SLOT[cat]);
  return c >= 0 ? c : SLOTS.length - 1;
}
