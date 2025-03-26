// Define global variables with better organization
const MapConfig = {
  grayLayer: L.tileLayer('https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token={accessToken}', {
    attribution: 'Map data &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, Imagery © <a href="https://www.mapbox.com/">Mapbox</a>',
    maxZoom: 18,
    id: 'mapbox/light-v9',
    tileSize: 512,
    zoomOffset: -1,
    accessToken: 'pk.eyJ1IjoiYWhtZWRzeWQiLCJhIjoiY2tsaWtvemlqMGE0czJ4cGxlaHMwZGUzNyJ9.ZqoUVoiuHS9LzOvahBnWKw'
  }),
  
  myLayer: L.tileLayer('https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token={accessToken}', {
    attribution: 'Map data &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, Imagery © <a href="https://www.mapbox.com/">Mapbox</a>',
    maxZoom: 22,
    id: 'ahmedsyd/cknc85hz519ln17o6t2pet38r',
    tileSize: 512,
    zoomOffset: -1,
    accessToken: 'pk.eyJ1IjoiYWhtZWRzeWQiLCJhIjoiY2tsaWttNXd3MGR6djJwbm0yNjh3dTVtdiJ9.LxSvLSwUs6MZdZxym8V9wA'
  })
};

// Initialize map with better defaults
const map = L.map('map', {
  zoomControl: true,
  center: [51.049999, -114.066666],
  zoom: 13,
  layers: [MapConfig.grayLayer]
}).setView([51.049999, -114.066666], 13);

// UI Elements
const loader = document.querySelector(".loader");
const allLinks = document.querySelectorAll("a");
const toggleLayerBtn = document.querySelector("#toggleLayer");

// Map Layers
let currentLayer = MapConfig.grayLayer;
const markers = L.markerClusterGroup();
const editableLayers = new L.FeatureGroup();
map.addLayer(editableLayers);

// State Variables
let userMarkerLayer = null;
let nearestHospitalLayer = null;
let selectedCircle = null;
let favoriteCircle = null;
let BestPath = null;
let hospitalsDict = {};
let traffics = null;
let hospitalsClinics = null;

// Initialize Draw Control
const drawControl = new L.Control.Draw({
  position: 'topright',
  draw: {
    polygon: false,
    circle: false,
    rectangle: false,
    polyline: false,
    marker: {
      allowIntersection: false,
      drawError: {
        color: '#e1e100',
        message: '<strong>Oh snap!</strong> you can\'t draw that!'
      },
      shapeOptions: {
        color: '#97009c'
      }
    }
  },
  edit: {
    featureGroup: editableLayers,
    remove: false
  }
});

map.addControl(drawControl);

// Helper Functions
function deleteAllLayers(removeSelected = true) {
  Object.values(map._layers).forEach(layer => {
    if (layer._path !== undefined) {
      try {
        if (!removeSelected && (layer === selectedCircle)) {
          return;
        }
        map.removeLayer(layer);
      } catch (e) {
        console.error("Problem removing layer:", e, layer);
      }
    }
  });
}

function toggleLoader(show) {
  loader.style.display = show ? "block" : "none";
  allLinks.forEach(link => {
    link.style.pointerEvents = show ? "none" : "auto";
  });
}

// Event Handlers
map.on('draw:created', function(e) {
  const { layerType, layer } = e;
  
  if (layerType === 'marker') {
    layer.bindPopup('User location');
    if (userMarkerLayer) {
      map.removeLayer(userMarkerLayer);
    }
    userMarkerLayer = layer;
  }
  
  editableLayers.addLayer(layer);
  
  if (BestPath) {
    deleteAllLayers(true);
  } else {
    deleteAllLayers(false);
  }
});

map.on('draw:deleted', function() {
  if (nearestHospitalLayer) {
    map.removeLayer(nearestHospitalLayer);
  }
  deleteAllLayers();
});

// Routing Functions
function getNumberOfTrafficSignals(pathPolyline) {
  if (!traffics?.features) return 0;
  
  const MAX_DISTANCE = 50; // Meters
  let count = 0;
  
  traffics.features.forEach(feature => {
    const trafficPoint = new L.LatLng(
      feature.geometry.coordinates[1], 
      feature.geometry.coordinates[0]
    );
    
    const nearestPoint = L.GeometryUtil.closest(
      map,
      pathPolyline,
      [feature.geometry.coordinates[1], feature.geometry.coordinates[0]]
    );
    
    if (trafficPoint.distanceTo(nearestPoint) < MAX_DISTANCE) {
      count++;
    }
  });
  
  return count;
}

function getDistanceOfPolyline(polylinePath) {
  let totalDistance = 0;
  let prevLatLng = null;
  
  polylinePath._latlngs.forEach(latlng => {
    if (prevLatLng) {
      totalDistance += prevLatLng.distanceTo(latlng);
    }
    prevLatLng = latlng;
  });
  
  return totalDistance;
}

async function getPathsBetweenTwoLocations(location1, location2, checkTraffic = false) {
  try {
    toggleLoader(true);
    
    const response = await $.ajax({
      url: `/direction/${location1.geometry.coordinates.join(',')}/${location2.geometry.coordinates.join(',')}`,
      method: 'GET'
    });

    if (!response.routes?.length) {
      throw new Error("No routes found");
    }

    let bestPath = null;
    let minTrafficCount = Infinity;
    const pathStyle = {
      color: '#3388ff',
      weight: 5,
      opacity: 0.7,
      dashArray: '10, 10',
      lineJoin: 'round'
    };

    response.routes.forEach(route => {
      const latLngs = route.legs[0].steps.flatMap(step => 
        L.PolylineUtil.decode(step.geometry)
      );
      
      const polyline = L.polyline(latLngs, pathStyle).addTo(map);
      
      if (checkTraffic) {
        const trafficCount = getNumberOfTrafficSignals(polyline);
        polyline.bindPopup(`Alternative route<br>Traffic signals: ${trafficCount}`);
        
        if (trafficCount < minTrafficCount) {
          minTrafficCount = trafficCount;
          bestPath = polyline;
        }
      } else {
        const distance = getDistanceOfPolyline(polyline);
        polyline.bindPopup(`Alternative route<br>Distance: ${distance.toFixed(2)} meters`);
        
        if (!bestPath || distance < getDistanceOfPolyline(bestPath)) {
          bestPath = polyline;
        }
      }
    });

    if (bestPath) {
      BestPath = bestPath;
      BestPath.setStyle({
        color: checkTraffic ? 'green' : 'red',
        weight: 7,
        dashArray: null
      });
      
      const popupContent = checkTraffic 
        ? `Best route with ${minTrafficCount} traffic signals`
        : `Shortest route: ${getDistanceOfPolyline(bestPath).toFixed(2)} meters`;
      
      BestPath.bindPopup(popupContent).openPopup();
    }

  } catch (error) {
    console.error("Routing error:", error);
    alert("Failed to calculate route. Please try again.");
  } finally {
    toggleLoader(false);
  }
}

// Initialize the application
document.addEventListener("DOMContentLoaded", () => {
  // Layer toggle
  toggleLayerBtn.onclick = function() {
    if (this.value === "Satellite") {
      map.removeLayer(MapConfig.grayLayer);
      map.addLayer(MapConfig.myLayer);
      this.value = "Gray";
      this.style.backgroundImage = "linear-gradient(to bottom, rgba(0,0,0,0) 10%, rgba(0,0,0,1)), url('/static/images/grayLayer.JPG')";
    } else {
      map.removeLayer(MapConfig.myLayer);
      map.addLayer(MapConfig.grayLayer);
      this.value = "Satellite";
      this.style.backgroundImage = "linear-gradient(to bottom, rgba(0,0,0,0) 10%, rgba(0,0,0,1)), url('/static/images/mylayer.JPG')";
    }
  };

  // Socket.io initialization
  toggleLoader(true);
  const socket = io.connect(`${location.protocol}//${document.domain}:${location.port}`);
  
  socket.on('connect', () => {
    socket.emit("read_data");
  });

  socket.on("map_data", data => {
    traffics = data.traffics;
    hospitalsClinics = data.hospitals_clinics;
    
    markers.clearLayers();
    map.closePopup();

    const hospIcon = L.icon({
      iconUrl: '/static/images/hospital_icon.png',
      iconSize: [38, 38]
    });

    hospitalsClinics.features.forEach(feature => {
      const loc = new L.LatLng(
        feature.geometry.coordinates[1],
        feature.geometry.coordinates[0]
      );
      
      const marker = L.marker(loc, { icon: hospIcon });
      const popupContent = `
        ${feature.properties.name}<br>
        <a href="javascript:void(0)" onclick="open_review('${feature.properties.comm_code}')">
          View/Add Review
        </a>
      `;
      
      hospitalsDict[feature.properties.comm_code] = loc;
      marker.bindPopup(popupContent);
      
      marker.on('dblclick', function() {
        if (selectedCircle && this.getLatLng().equals(selectedCircle.getLatLng())) {
          map.removeLayer(selectedCircle);
          selectedCircle = null;
          return;
        }
        
        if (selectedCircle) {
          map.removeLayer(selectedCircle);
        }
        
        selectedCircle = L.circleMarker(this.getLatLng(), {
          radius: 25,
          color: "green"
        }).addTo(map);
      });
      
      markers.addLayer(marker);
    });

    map.addLayer(markers);
    toggleLoader(false);
  });

  // Favorite links
  document.querySelectorAll(".favoriteLink").forEach(link => {
    link.onclick = function() {
      const codeValue = this.getAttribute('value');
      const circleLoc = hospitalsDict[codeValue];
      
      if (favoriteCircle) {
        map.removeLayer(favoriteCircle);
      }
      
      setTimeout(() => map.setView(circleLoc, 13), 100);
      favoriteCircle = L.circleMarker(circleLoc, { radius: 25 }).addTo(map);
    };
  });
});

// Global functions
function open_review(hospital_clinic_code) {
  map.closePopup();
  location.href = Flask.url_for('hospital_clinic_details', { code: hospital_clinic_code });
}

function pathToNearest(checkTraffic) {
  if (!userMarkerLayer) {
    alert("Please specify your location first");
    return;
  }
  
  const loc = userMarkerLayer.getLatLng();
  const userLocation = {
    type: "Feature",
    geometry: {
      type: "Point",
      coordinates: [loc.lng, loc.lat]
    }
  };
  
  if (nearestHospitalLayer) {
    map.removeLayer(nearestHospitalLayer);
  }
  
  const nearestHospital = turf.nearest(userLocation, hospitalsClinics);
  nearestHospitalLayer = L.geoJSON(nearestHospital, {
    pointToLayer: (feature, latlng) => L.circleMarker(latlng, {
      radius: 25,
      fillColor: "#ff7800",
      color: "#000",
      weight: 1,
      opacity: 1,
      fillOpacity: 0.8
    })
  }).addTo(map);
  
  getPathsBetweenTwoLocations(userLocation, nearestHospital, checkTraffic);
}

function pathToSelected(checkTraffic) {
  if (!selectedCircle) {
    alert("Please select a hospital/clinic first");
    return;
  }
  
  if (!userMarkerLayer) {
    alert("Please specify your location first");
    return;
  }
  
  const userLoc = userMarkerLayer.getLatLng();
  const userLocation = {
    type: "Feature",
    geometry: {
      type: "Point",
      coordinates: [userLoc.lng, userLoc.lat]
    }
  };
  
  const selectedLoc = selectedCircle.getLatLng();
  const selectedLocation = {
    type: "Feature",
    geometry: {
      type: "Point",
      coordinates: [selectedLoc.lng, selectedLoc.lat]
    }
  };
  
  getPathsBetweenTwoLocations(userLocation, selectedLocation, checkTraffic);
}