// Pure rules shared by the map UI and its regression fixtures. Units: g, s, m.
const MapUIRules = (() => {
  function dwellLimit(constraints) {
    let seconds = Infinity;
    for (const { budget, used, rate } of constraints) {
      if (![budget, used, rate].every(Number.isFinite) || rate < 0 || used < 0) return null;
      if (used > budget + 1e-8) return null;
      if (rate > 0) seconds = Math.min(seconds, Math.max(0, budget - used) / rate);
    }
    return Number.isFinite(seconds) ? Math.floor(seconds) : null;
  }
  const zone = r => !Number.isFinite(r) ? 'unknown' : r <= .1 ? 'red' : r <= .2 ? 'yellow' : 'blue';
  const angleDelta = (a,b) => ((a-b+540)%360)-180;
  function gesture(start, next, view) {
    const a=start[0],b=start[1],c=next[0],d=next[1];
    const midpoint=pts=>({x:(pts[0].x+pts[1].x)/2,y:(pts[0].y+pts[1].y)/2});
    const old=midpoint(start),now=midpoint(next),anchor=unproject(old.x,old.y,view);
    const initialDistance=Math.hypot(b.x-a.x,b.y-a.y);
    const turn=angleDelta(Math.atan2(d.y-c.y,d.x-c.x)*180/Math.PI,Math.atan2(b.y-a.y,b.x-a.x)*180/Math.PI);
    const result={...view,k:Math.max(1,Math.min(10,view.k*Math.hypot(d.x-c.x,d.y-c.y)/Math.max(1,initialDistance))),angle:view.angle+turn};
    const q=project(anchor.x,anchor.y,result);result.cx+=now.x-q.x;result.cy+=now.y-q.y;return result;
  }
  function project(x, y, view) {
    const a = view.angle * Math.PI / 180, c = Math.cos(a), s = Math.sin(a);
    const dx = (x - view.w / 2) * view.k, dy = (y - view.h / 2) * view.k;
    return { x: view.cx + c * dx - s * dy, y: view.cy + s * dx + c * dy };
  }
  function unproject(x, y, view) {
    const a = -view.angle * Math.PI / 180, c = Math.cos(a), s = Math.sin(a);
    const dx = x - view.cx, dy = y - view.cy;
    return { x: (c * dx - s * dy) / view.k + view.w / 2, y: (s * dx + c * dy) / view.k + view.h / 2 };
  }
  const normalizeLon=lon=>((lon+180)%360+360)%360-180;
  const overviewToLonLat=(x,y,width,height)=>({lon:normalizeLon(x/width*360-180),lat:Math.max(-90,Math.min(90,90-y/height*180))});
  const lonLatToOverview=(lon,lat,width,height)=>({x:(normalizeLon(lon)+180)/360*width,y:(90-Math.max(-90,Math.min(90,lat)))/180*height});
  return { normalizeLon,overviewToLonLat,lonLatToOverview,dwellLimit, zone, project, unproject, angleDelta, gesture };
})();
