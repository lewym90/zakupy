// Jeden zestaw ikon liniowych 24 × 24 zamiast emoji: ten sam rysunek na każdym telefonie.
const P = {
  ryby: '<path d="M3 12c3-5 8-6.5 12-4.5 1.8.9 3 2.7 3 4.5s-1.2 3.6-3 4.5C11 18.5 6 17 3 12Z"/><path d="m18 12 3-3v6z"/><circle cx="8" cy="11" r=".6"/>',
  wedliny: '<path d="M5 19c-2-2-1.5-5 1-7.5l5-5C13.5 4 16.5 3.5 18.5 5.5s1.5 5-1 7.5l-5 5C10 20.5 7 21 5 19Z"/><circle cx="14.5" cy="9.5" r="1.2"/><circle cx="9.5" cy="14.5" r="1.2"/>',
  mieso: '<path d="M13.5 4c4 0 6.5 2.5 6.5 6 0 5-4.5 9.5-9.5 10-3.5.3-6.5-2-6.5-5.5 0-2.5 1.5-4 3.5-5 2-1 2.5-2 3-3.5.3-1.2 1.5-2 3-2Z"/><circle cx="14" cy="10" r="2"/>',
  nabial: '<path d="M8 3h8v3l2 4v10a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V10l2-4z"/><path d="M6 13h12M8 6h8"/>',
  warzywa: '<path d="M12 8c-4-2.5-8 .5-8 5 0 4 3 8 5.5 8 1 0 1.5-.5 2.5-.5s1.5.5 2.5.5c2.5 0 5.5-4 5.5-8 0-4.5-4-7.5-8-5Z"/><path d="M12 8c0-2 .8-3.8 2.5-5"/>',
  pieczywo: '<path d="M6 10a3 3 0 0 1-1-5.8C6 3.5 8 3 12 3s6 .5 7 1.2A3 3 0 0 1 18 10v9a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1z"/>',
  mrozonki: '<path d="M12 3v18M4.2 7.5l15.6 9M19.8 7.5l-15.6 9"/><path d="m9.5 4.5 2.5 2 2.5-2M9.5 19.5l2.5-2 2.5 2"/>',
  napoje: '<path d="M10 3h4v3.5c0 1 2.5 2 2.5 5V20a1 1 0 0 1-1 1h-7a1 1 0 0 1-1-1v-8.5c0-3 2.5-4 2.5-5z"/><path d="M7.5 14h9"/>',
  kawa: '<path d="M5 9h12v6a5 5 0 0 1-5 5h-2a5 5 0 0 1-5-5z"/><path d="M17 11h1.5a2.5 2.5 0 0 1 0 5H16.5M9 3v2.5M13 3v2.5"/>',
  alkohol: '<path d="M8 3h8l.8 5a4.8 4.8 0 0 1-9.6 0zM12 13v8M8.5 21h7M7.3 8h9.4"/>',
  slodycze: '<path d="M4 4h16v16H4zM4 9.3h16M4 14.7h16M9.3 4v16M14.7 4v16"/>',
  spizarnia: '<path d="M7 7h10M8 3.5h8a1 1 0 0 1 1 1V7l1 2v10.5a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V9l1-2V4.5a1 1 0 0 1 1-1Z"/><path d="M6 12h12v5H6z"/>',
  chemia: '<path d="M9 8h6l1 3v9a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1v-9zM10 8V5h3l4 1.5M10 5H8"/>',
  zwierzeta: '<circle cx="6.5" cy="11" r="1.8"/><circle cx="10" cy="6.5" r="1.8"/><circle cx="14.5" cy="6.5" r="1.8"/><circle cx="18" cy="11" r="1.8"/><path d="M12.2 11c-2.5 0-5 3.5-5 6 0 1.8 1.3 2.7 2.7 2.7 1 0 1.4-.5 2.3-.5s1.3.5 2.3.5c1.4 0 2.7-.9 2.7-2.7 0-2.5-2.5-6-5-6Z"/>',
  inne: '<path d="M6 8h12l1 12a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1zM9 8V6a3 3 0 0 1 6 0v2"/>',
  aparat: '<path d="M4 8h3l1.5-2.5h7L17 8h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Z"/><circle cx="12" cy="13.5" r="3.5"/>',
  dalej: '<path d="m9 5 7 7-7 7"/>',
};
export const ic = (id, cls = '') => `<svg class="ic ${cls}" viewBox="0 0 24 24" aria-hidden="true">${P[id] || P.inne}</svg>`;
