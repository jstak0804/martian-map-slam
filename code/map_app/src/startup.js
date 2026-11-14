
  // QA-only read handles (browser checks in tests/browser_qa.mjs). Not used by the product flow.
  Object.defineProperties(window.EVA_DEBUG, Object.getOwnPropertyDescriptors({ get UI() { return UI; }, get EVA() { return EVA; }, get SITE_I() { return SITE_I; }, get siteGeneration() { return siteGeneration; }, get overlayRevision() { return overlayRevision; }, get workerPending() { return WK_CB.size; }, get workerAlive() { return !!WK; }, get frame() { return simFrame(); }, get LEGS() { return LEGS; }, loadSite: (i) => loadSite(i), modelKey: () => modelKey() }));
  loadSite(START, devHash).then(() => {  if (HASH === "#selftest" && SETS) selfTest(); })
    .catch((err) => { $("loading").hidden = false; $("loading").textContent = "Could not load map data. Open this file in a current Chrome, Edge, Safari or Firefox browser. (" + err.message + ")"; });
})();
