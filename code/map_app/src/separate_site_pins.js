// Keep every marker at its projected geographic position, even when overlapping.
function uiClusterPins(layer,sel){
  layer.querySelectorAll('.map-pin-cluster,.site-pin-leaders').forEach(el=>el.remove());
  layer.querySelectorAll('.map-target-pin').forEach(pin=>pin.classList.remove('clustered'));
}
