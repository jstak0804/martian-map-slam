
async function uiCanSelectTarget(cell){
  const reject=(ko,en)=>{uiToast(uiText(ko,en));return false;};
  if(!H||cell<0||cell>=N||!(FLAGS[cell]&1))return reject('선택 불가: 지형 자료가 없는 위치입니다','Cannot select: no terrain data');
  if(!(FLAGS[cell]&8)||((state.nofall||strictEva())&&CLS[cell]===2))return reject('선택 불가: 통행이 제한된 지형입니다','Cannot select: impassable terrain');
  const back=setNow();
  if(!back)return reject('경로를 계산 중입니다. 잠시 후 다시 선택하세요','Routes are updating. Try again shortly');
  if(!Number.isFinite(back.o2[cell])||back.o2[cell]<0)return reject('선택 불가: 기지로 복귀할 경로가 없습니다','Cannot select: no return route to base');
  const generation=siteGeneration,key=legKey(state.base),base=state.base;
  try{
    const forward=LEGS.get(key)||await wkDijkstra(base,false,state.nofall);
    if(generation!==siteGeneration||base!==state.base||key!==legKey(state.base))return reject('지도가 변경되었습니다. 다시 선택하세요','Map changed. Select the target again');
    LEGS.set(key,forward);
    if(!Number.isFinite(forward.o2[cell])||forward.o2[cell]<0)return reject('선택 불가: 기지에서 도달할 경로가 없습니다','Cannot select: no route from base');
    return true;
  }catch{return reject('경로 확인에 실패했습니다. 다시 시도하세요','Route check failed. Please try again');}
}
