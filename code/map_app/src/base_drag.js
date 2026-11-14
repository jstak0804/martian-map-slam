
// Delegation survives marker recreation when switching regions.
(() => {
  let moving = null;
  const style = document.createElement('style');
  style.textContent = '#map-base-pin{pointer-events:auto;cursor:grab;touch-action:none;z-index:4} .base-drag-ghost{position:fixed;pointer-events:none;z-index:1000;transform:translate(-50%,-50%);padding:9px;border-radius:10px;background:#183d35;color:#b2f4d8;border:2px solid currentColor;font:12px sans-serif}';
  document.head.append(style);
  document.addEventListener('pointerdown', e => {
    const pin = e.target.closest?.('#map-base-pin');
    if (!pin || e.button !== 0) return;
    e.preventDefault(); e.stopImmediatePropagation();
    stopSim();
    const ghost = document.createElement('div');
    ghost.className = 'base-drag-ghost'; ghost.textContent = 'Move base';
    ghost.style.left = e.clientX+'px'; ghost.style.top = e.clientY+'px';
    document.body.append(ghost);
    moving = {id:e.pointerId, ghost, site:SITE_I};
    pin.setPointerCapture(e.pointerId);
  }, true);
  document.addEventListener('pointermove', e => {
    if (!moving || moving.id !== e.pointerId) return;
    e.preventDefault(); e.stopImmediatePropagation();
    moving.ghost.style.left = e.clientX+'px'; moving.ghost.style.top = e.clientY+'px';
    const i = cellAt(e);
    moving.ghost.style.color = i>=0 && FLAGS[i]&1 ? '#b2f4d8' : '#ff8178';
  }, true);
  const end = (e, cancel) => {
    if (!moving || moving.id !== e.pointerId) return;
    e.preventDefault(); e.stopImmediatePropagation();
    const previous = moving; moving = null; previous.ghost.remove(); dragMoved = true;
    if (cancel || previous.site !== SITE_I) return;
    const rect = wrap.getBoundingClientRect(), i = cellAt(e);
    if (e.clientX<rect.left || e.clientX>rect.right || e.clientY<rect.top || e.clientY>rect.bottom || i<0 || !(FLAGS[i]&1)) {
      uiToast('Place base inside the mapped terrain'); return;
    }
    const view = {angle:UI.angle, headingUp:UI.headingUp};
    state.base = i; activePreset = ''; SIMSIG = ''; uiClear();
    // uiClear hides markers for region changes. A base move stays in the
    // same region: restore the view and pins before async route calculation.
    UI.angle = view.angle; UI.headingUp = view.headingUp;
    uiApplyZoom(false);
    update();
    uiToast('Base moved — trip recalculated');
  };
  document.addEventListener('pointerup', e => end(e,false), true);
  document.addEventListener('pointercancel', e => end(e,true), true);
})();
