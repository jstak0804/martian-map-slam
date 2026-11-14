// Keep the existing controls and handlers; change only their presentation.
(() => {
  const icons = {
    'map-world': ['Global map', '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18M5 7h14M5 17h14"/>'],
    'map-sites': ['Sites', '<path d="M5 21V3m0 1c5-4 9 4 15 0v10c-6 4-10-4-15 0"/>'],
    'map-roadview': ['Rover photos', '<path d="M3 7h4l2-3h6l2 3h4v13H3z"/><circle cx="12" cy="13" r="4"/>'],
    'map-settings': ['Settings', '<path d="m9 3-1 3-3 1 1 3-2 2 2 2-1 3 3 1 1 3h6l1-3 3-1-1-3 2-2-2-2 1-3-3-1-1-3z"/><circle cx="12" cy="12" r="3"/>'],
    'map-visor': ['Visor', '<path d="M2 7c6-3 14-3 20 0l-2 11h-5l-3-4-3 4H4zM5 9h14"/>'],
    'map-evidence': ['Observations', '<path d="M5 3h14v18H5zM8 7h8M8 11h8M8 15h5"/>'],
    'map-event': ['Block test', '<path d="m12 3 10 18H2zM12 9v5M12 17v1"/>']
  };
  for (const [id, [label, path]] of Object.entries(icons)) {
    const button = $(id);
    button.innerHTML = `<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${path}</svg>`;
    button.title = label;
    button.setAttribute('aria-label', label);
  }
  document.querySelector('.map-brand')?.remove();
  const evidence = $('map-evidence');
  evidence.textContent = 'Observations';
  evidence.classList.add('map-button');
  const research = document.createElement('details');
  research.id = 'map-research-settings';
  const researchTitle = document.createElement('summary');
  researchTitle.textContent = 'Data and validation';
  research.append(researchTitle, evidence);
  $('map-drawer').append(research);
  const visor = $('map-visor');
  visor.classList.add('map-button', 'map-shell', 'standalone-visor');
  $('map-ui').append(visor);
  const style = document.createElement('style');
  style.textContent = `
    .map-top { justify-content:center; }
    .map-actions { max-width:100%; flex-wrap:wrap; justify-content:center; }
    .map-actions button { display:inline-flex; align-items:center; justify-content:center; box-sizing:border-box; flex:0 0 44px; width:44px; height:44px; padding:10px; }
    .map-actions button[hidden], #map-event { display:none!important; }
    .map-actions button svg { flex-shrink:0; }
    #map-research-settings { margin:12px 0; padding:12px; border:1px solid #ffffff20; border-radius:10px; }
    #map-research-settings summary { cursor:pointer; margin-bottom:10px; }
    #map-research-settings button[hidden] { display:none; }
    .standalone-visor { position:fixed; right:24px; bottom:52px; width:54px; height:54px; display:flex; align-items:center; justify-content:center; pointer-events:auto; background:#182b36; border:1px solid #8fc5cd; border-radius:16px; z-index:12; }
    .standalone-visor svg { width:30px; height:30px; }
    .map-actions button:focus-visible,.standalone-visor:focus-visible { outline:2px solid #bceef6; outline-offset:3px; }
    @media(max-width:600px) { .map-actions { gap:3px; } .map-actions button { flex-basis:40px; width:40px; height:40px; padding:8px; } .standalone-visor { right:12px; bottom:calc(var(--planning-height,270px) + 24px); } }
  `;
  document.head.append(style);
  const planning=document.querySelector('.map-bottom');
  new ResizeObserver(()=>document.documentElement.style.setProperty('--planning-height',planning.getBoundingClientRect().height+'px')).observe(planning);
})();
