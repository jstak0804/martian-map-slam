const path=require('node:path');const ROOT=path.resolve(__dirname,'../..');
const fs=require('fs'),assert=require('assert/strict');
const s=fs.readFileSync(path.join(ROOT,'code/map_app/src/visor_navigation.js'),'utf8');
assert(!s.includes('g.quadraticCurveTo('),'Visor must not draw route guidance curves');
assert(!s.includes('TURN RIGHT')&&!s.includes('TURN LEFT'),'Visor must not draw directional arrows');
assert(s.includes('WAYPOINT')&&s.includes('drawBar('),'Waypoint distance and resources must remain');
console.log('PASS: no guidance curve/arrows; distance and resources preserved');
