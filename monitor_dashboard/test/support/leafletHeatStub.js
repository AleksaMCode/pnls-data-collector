// A stand-in for the leaflet.heat plugin, which draws on a canvas jsdom doesn't have. It records each
// heat layer the dashboard creates.
import L from 'leaflet';

export const heatLayers = [];

L.heatLayer = (points, options) => {
  const layer = {
    points,
    options,
    addTo(map) {
      map.addLayer(layer);
      return layer;
    },
  };
  heatLayers.push(layer);
  return layer;
};

export default {};
