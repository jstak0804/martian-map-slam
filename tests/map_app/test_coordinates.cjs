const path = require('node:path');
const fs = require('node:fs');
const vm = require('node:vm');
const zlib = require('node:zlib');
const assert = require('node:assert/strict');
const ROOT = path.resolve(__dirname, '../..');
const metadata = zlib.gunzipSync(fs.readFileSync(path.join(ROOT, 'code/map_app/assets/georeference.json.gz'))).toString('utf8');
const source = fs.readFileSync(path.join(ROOT, 'code/map_app/src/map_coordinates.js'), 'utf8')
  .replace('@@JSON:georeference@@', metadata).split('(() => {')[0];
const context = {};
vm.createContext(context);
vm.runInContext(source, context);
for (const [region, projection] of Object.entries(JSON.parse(metadata))) {
  const location = context.uiGridToLonLat(290, 350, projection);
  const grid = context.uiLonLatToGrid(location.lon, location.lat, projection);
  assert(Math.abs(grid.x - 290) < 1e-7 && Math.abs(grid.y - 350) < 1e-7, region);
  assert(location.lon >= -180 && location.lon <= 180, region);
  if (region === 'aram') {
    assert(Math.abs(location.lat - 2.297) < .02);
    assert(location.lon < 0 && location.lon > -21);
  }
}
console.log('PASS: three-region coordinate projection and antimeridian-safe inverse');
