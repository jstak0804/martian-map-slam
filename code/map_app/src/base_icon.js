
function uiBaseIcon(){
  const pin=$('map-base-pin');if(!pin)return;
  const active=(simFrame()?.m??0)>0;
  const key=active?'pin':'circle';if(pin.dataset.houseIcon===key)return;
  pin.dataset.houseIcon=key;
  const house='<path d="M10 19L20 10L30 19V21H27V32H22V25Q20 22 18 25V32H13V21H10Z" fill="white" stroke="white" stroke-linejoin="round" stroke-width="2"/>';
  const shape=active?'<path d="M20 47C16 41 3 30 3 19A17 17 0 0 1 37 19C37 30 24 41 20 47Z" fill="#111820" stroke="white" stroke-width="2"/><circle cx="20" cy="19" r="13" fill="white"/><g transform="translate(6 5) scale(.7)">'+house.replaceAll('white','#111820')+'</g>':'<circle cx="20" cy="21" r="18" fill="#111820" stroke="white" stroke-width="2"/>'+house;
  const svg=pin.querySelector('svg');svg.setAttribute('viewBox',active?'0 0 40 50':'0 0 40 42');svg.innerHTML=shape;
  pin.title=uiText('기지 · 드래그해서 이동','Base · drag to move');
}
