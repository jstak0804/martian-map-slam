
(() => {
  const drawer=$('map-drawer');
  const section=(label,id)=>{
    const details=document.createElement('details');details.className='settings-section';details.id=id;
    const summary=document.createElement('summary');summary.textContent=label;details.append(summary);return details;
  };
  const resources=section('Resources and model','settings-resources');
  const analysis=section('Map and analysis','settings-analysis');
  const help=section('Controls and reference','settings-help');
  const languages=section('Languages','settings-languages');
  languages.querySelector('summary').insertAdjacentHTML('afterbegin','<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" aria-hidden="true"><circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/></svg> ');
  const select=document.createElement('select');select.setAttribute('aria-label','Interface language');
  select.id='settings-language';
  select.innerHTML='<option value="en">English</option><option value="ko">한국어</option>';
  languages.append(select);
  for(const node of [...drawer.children]){
    if(node.classList.contains('map-drawer-head')||node.id==='map-research-settings')continue;
    if(node.classList.contains('panel'))resources.append(node);
    else if(node.classList.contains('modebar')||node.tagName==='DIV')analysis.append(node);
    else help.append(node);
  }
  const research=$('map-research-settings');research.classList.add('settings-section');
  drawer.append(languages,resources,analysis,research,help);
  // One expanded group at a time; native details preserve keyboard access.
  for(const group of drawer.querySelectorAll(':scope > details'))group.addEventListener('toggle',()=>{
    if(group.open)for(const other of drawer.querySelectorAll(':scope > details'))if(other!==group)other.open=false;
  });
  const style=document.createElement('style');style.textContent=`
    #map-drawer>.settings-section { margin:8px 0; padding:0; border:1px solid #ffffff20; border-radius:10px; }
    #map-drawer>.settings-section>summary { padding:14px; margin:0; cursor:pointer; font-size:13px; }
    .settings-section>summary svg { vertical-align:middle; }
    .settings-section> :not(summary) { margin:10px 12px; }
    .settings-section>.panel,.settings-section>.modebar,.settings-section>div[style] { display:grid!important; }
    .settings-section select { background:#263139; color:#e9eeec; border:1px solid #ffffff30; padding:8px; border-radius:8px; }
  `;document.head.append(style);
})();
