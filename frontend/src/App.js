import { MapContainer, TileLayer, GeoJSON, Marker, Polyline, Popup, Tooltip, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useState, useEffect } from "react";
import "./App.css";
import countriesData from "./data/countries.json";
import { reportDisaster, getActiveDisasters, getFireStations, pollDisasterAnalysis, resolveDisaster, getDispatchDecisions, getAnalytics, getHospitals } from "./services/api";
import axios from "axios";

const API_BASE_URL = "http://localhost:8000/api";

// Fix default leaflet marker icon
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: require("leaflet/dist/images/marker-icon-2x.png"),
  iconUrl:       require("leaflet/dist/images/marker-icon.png"),
  shadowUrl:     require("leaflet/dist/images/marker-shadow.png"),
});

const incidentIcon = new L.DivIcon({
  className: "",
  html: `<div style="width:42px;height:42px;border-radius:50%;background:rgba(255,200,0,0.9);
    border:3px solid #ff9500;display:flex;align-items:center;justify-content:center;
    font-size:22px;box-shadow:0 0 16px rgba(255,180,0,0.7);">⚠️</div>`,
  iconSize: [42, 42],
  iconAnchor: [21, 21],
});

const fireIcon = new L.DivIcon({
  className: "",
  html: `<div style="width:38px;height:38px;border-radius:50%;background:#e63946;
    border:3px solid #fff;display:flex;align-items:center;justify-content:center;font-size:18px;
    box-shadow:0 2px 8px rgba(230,57,70,0.6);">🚒</div>`,
  iconSize: [38, 38],
  iconAnchor: [19, 19],
});

const hospitalIcon = new L.DivIcon({
  className: "",
  html: `<div style="width:38px;height:38px;border-radius:50%;background:#1d7aff;
    border:3px solid #fff;display:flex;align-items:center;justify-content:center;font-size:18px;
    box-shadow:0 2px 8px rgba(29,122,255,0.6);">🏥</div>`,
  iconSize: [38, 38],
  iconAnchor: [19, 19],
});

// Auto-pan map to incident location
function FlyTo({ coords }) {
  const map = useMap();
  if (coords) map.flyTo(coords, 14, { duration: 1.2 });
  return null;
}

// Captures map clicks on the title page map picker
function MapClickHandler({ onMapClick }) {
  useMapEvents({
    click(e) {
      onMapClick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

const pinIcon = new L.DivIcon({
  className: "",
  html: `<div style="width:28px;height:28px;border-radius:50%;background:rgba(255,180,50,0.9);
    border:2px solid #fff;display:flex;align-items:center;justify-content:center;font-size:14px;
    box-shadow:0 0 12px rgba(255,180,50,0.6);">📍</div>`,
  iconSize: [28, 28],
  iconAnchor: [14, 14],
});

const RESOURCE_ICONS = {
  "Fire Trucks": "🚒",
  Ambulances:    "🚑",
  "Police Units":"🚓",
  Others:        "🚧",
};

const CHICAGO_CENTER = [41.8781, -87.6298];
const CHICAGO_ZOOM   = 10;

const INCIDENT_DETAIL_LABELS = {
  severity:    "Severity Score",
  population:  "Population / Exposure",
  routing:     "Routing & Travel Time",
  feasibility: "Feasibility Score",
  ambulances:  "Ambulances Ready?",
  weather:     "Weather Constraints?",
};

// ── Dummy station pins ─────────────────────────────────────────
const DUMMY_STATIONS = [
  { id: 1, name: "Station Alpha — Loop",        lat: 41.8827, lng: -87.6233, fireTrucks: 4, ambulances: 3, others: 2 },
  { id: 2, name: "Station Bravo — Lincoln Park", lat: 41.9214, lng: -87.6513, fireTrucks: 2, ambulances: 5, others: 1 },
  { id: 3, name: "Station Charlie — Hyde Park",  lat: 41.7943, lng: -87.5907, fireTrucks: 3, ambulances: 2, others: 4 },
  { id: 4, name: "Station Delta — Wicker Park",  lat: 41.9088, lng: -87.6789, fireTrucks: 5, ambulances: 4, others: 2 },
  { id: 5, name: "Station Echo — Pilsen",        lat: 41.8556, lng: -87.6594, fireTrucks: 2, ambulances: 3, others: 3 },
  { id: 6, name: "Station Foxtrot — Uptown",     lat: 41.9645, lng: -87.6527, fireTrucks: 3, ambulances: 2, others: 1 },
];

const createStationIcon = () =>
  L.divIcon({
    className: "",
    html: `
      <div style="position:relative;width:20px;height:20px;display:flex;align-items:center;justify-content:center;">
        <div style="position:absolute;inset:0;border-radius:50%;border:1.5px solid rgba(80,160,255,0.5);
          animation:pinPulse 2.4s ease-out infinite;pointer-events:none;"></div>
        <div style="width:9px;height:9px;border-radius:50%;background:#60a8ff;
          box-shadow:0 0 0 2px rgba(80,160,255,0.25),0 0 10px rgba(80,160,255,0.7);
          position:relative;z-index:2;flex-shrink:0;"></div>
        <style>@keyframes pinPulse{0%{transform:scale(1);opacity:0.9;}70%{transform:scale(2.6);opacity:0;}100%{transform:scale(2.6);opacity:0;}}</style>
      </div>`,
    iconSize: [20, 20],
    iconAnchor: [10, 10],
    tooltipAnchor: [16, 0],
  });

// ── Title Page Option Configs ──────────────────────────────────

export default function App() {
  // ── Title page ────────────────────────────────────────────────
  const [showTitlePage,   setShowTitlePage]   = useState(true);
  const [titleMode,       setTitleMode]       = useState(null); // "type" | "map"
  const [titleLocation,   setTitleLocation]   = useState("");
  const [titleDesc,       setTitleDesc]       = useState("");
  const [titlePin,        setTitlePin]        = useState(null); // {lat, lng}
  const [titleError,      setTitleError]      = useState("");
  const [titleSubmitting, setTitleSubmitting] = useState(false);

  // ── Core state ────────────────────────────────────────────────
  const [selected,  setSelected]  = useState(null);
  const [view,      setView]      = useState("country");
  const [modal,     setModal]     = useState(null);
  const [resourceModal, setResourceModal] = useState(null);
  const [resourceFields, setResourceFields] = useState({
    "Fire Trucks":  { total: "", nearestWithin100m: "", estimatedResponseTime: "" },
    Ambulances:     { total: "", nearestWithin100m: "", estimatedResponseTime: "" },
    "Police Units": { total: "", nearestWithin100m: "", estimatedResponseTime: "" },
    Others:         { total: "", nearestWithin100m: "", estimatedResponseTime: "" },
  });

  const updateResourceField = (resource, field, value) =>
    setResourceFields(prev => ({ ...prev, [resource]: { ...prev[resource], [field]: value } }));

  const [saved,    setSaved]    = useState(false);
  const [draft,    setDraft]    = useState({ location: "", description: "", predicted: "" });
  const [severityInput, setSeverityInput] = useState("");
  const [severityScore, setSeverityScore] = useState("");
  const [severityNotes, setSeverityNotes] = useState("");
  const [populationData, setPopulationData] = useState({ area: "", buildings: "", type: "", people: "" });
  const [routingData,    setRoutingData]    = useState({ station: "", eta: "", traffic: "", blocks: "" });
  const [feasibilityData, setFeasibilityData] = useState("");
  const [ambulanceData,   setAmbulanceData]   = useState("");
  const [weatherData,     setWeatherData]     = useState("");
  const [activeDisasters,   setActiveDisasters]   = useState([]);
  const [resolvedDisasters, setResolvedDisasters] = useState([]);
  const [fireStations,      setFireStations]      = useState([]);
  const [submitting,  setSubmitting]  = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [analysisResult, setAnalysisResult] = useState(null);
  const [analyzing,      setAnalyzing]      = useState(false);
  const [resolveTarget,  setResolveTarget]  = useState(null);
  const [resolutionNotes, setResolutionNotes] = useState("");
  const [resolving,       setResolving]       = useState(false);
  const [dispatchData,    setDispatchData]    = useState([]);
  const [analyticsData,   setAnalyticsData]   = useState(null);
  const [hospitals,       setHospitals]       = useState([]);
  const [newIncidentMode, setNewIncidentMode] = useState(null); // null | "type" | "map"
  const [newPin,          setNewPin]          = useState(null);
  const [lastIncidentCoords, setLastIncidentCoords] = useState(null);
  const [incidentListPage, setIncidentListPage] = useState(0);
  const INCIDENTS_PER_PAGE = 10; // persists pin on map

  useEffect(() => {
    if (view === "incidents") fetchActiveDisasters();
    if (view === "resolved")  fetchResolvedDisasters();
    if (view === "analytics") fetchAnalytics();
    if (view === "resources") { fetchHospitals(); fetchFireStations(); }
  }, [view]);

  useEffect(() => { fetchFireStations(); }, []);

  const fetchActiveDisasters = async () => {
    try   { const r = await getActiveDisasters(); setActiveDisasters(r.data); }
    catch  { console.error("Failed to fetch active disasters"); }
  };
  const fetchResolvedDisasters = async () => {
    try   { const r = await axios.get(`${API_BASE_URL}/disasters/resolved/`); setResolvedDisasters(r.data); }
    catch  { console.error("Failed to fetch resolved disasters"); }
  };
  const fetchFireStations = async () => {
    try   { const r = await getFireStations(); setFireStations(r.data); }
    catch  { console.error("Failed to fetch fire stations"); }
  };
  const fetchAnalytics = async () => {
    try   { const r = await getAnalytics(); setAnalyticsData(r.data); }
    catch  { console.error("Failed to fetch analytics"); }
  };
  const fetchHospitals = async () => {
    try   { const r = await getHospitals(); setHospitals(r.data.hospitals || []); }
    catch  { console.error("Failed to fetch hospitals"); }
  };

  // Submit from title page — goes straight to analysis
  const handleTitleSubmit = async () => {
    const location = titleLocation.trim();
    const description = titleDesc.trim();
    if (!location && !titlePin) { setTitleError("Please enter a location or pick one on the map."); return; }
    setTitleError("");
    setTitleSubmitting(true);
    setAnalysisResult(null);
    setDispatchData([]);
    try {
      const payload = {
        disaster_type: "fire",
        address:       location || `${titlePin.lat.toFixed(5)}, ${titlePin.lng.toFixed(5)}`,
        description:   description,
      };
      // If map pin was used, pass coords directly so backend skips geocoding
      if (titlePin) {
        payload.latitude  = titlePin.lat;
        payload.longitude = titlePin.lng;
      }
      const response = await reportDisaster(payload);
      const disasterId = response.data.disaster_id;
      setShowTitlePage(false);
      setAnalyzing(true);
      setView("analysis");
      pollDisasterAnalysis(disasterId, (disaster) => {
        setAnalysisResult(disaster);
        if (disaster.status === "analyzed") {
          setAnalyzing(false);
          fetchActiveDisasters();
          if (disaster.latitude && disaster.longitude) {
            setLastIncidentCoords([disaster.latitude, disaster.longitude]);
          }
          pollDispatchDecisions(disaster.id);
        }
      });
    } catch (err) {
      setTitleError("Failed to submit. Is the backend running?");
    } finally {
      setTitleSubmitting(false);
    }
  };

  // Poll dispatch decisions until both fire and ambulance records exist (max 3 minutes)
  const pollDispatchDecisions = (disasterId, maxAttempts = 36) => {
    let attempts = 0;
    const interval = setInterval(async () => {
      attempts++;
      try {
        const res = await getDispatchDecisions(disasterId);
        const decisions = res.data.decisions || [];
        const hasFire = decisions.some(d => d.dispatch_type === "fire");
        const hasAmbulance = decisions.some(d => d.dispatch_type === "ambulance");
        // Update UI as soon as we have anything, but keep polling until both arrive
        if (decisions.length > 0) {
          setDispatchData(decisions);
        }
        if ((hasFire && hasAmbulance) || attempts >= maxAttempts) {
          clearInterval(interval);
        }
      } catch (err) {
        console.error("Dispatch poll error:", err);
        if (attempts >= maxAttempts) clearInterval(interval);
      }
    }, 5000);
    return interval;
  };

  // Reverse geocode a lat/lng to a street address
  const reverseGeocode = async (lat, lng) => {
    try {
      const res = await axios.get(
        `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`,
        { headers: { "Accept-Language": "en" } }
      );
      const addr = res.data.display_name || `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
      setTitleLocation(addr);
    } catch {
      setTitleLocation(`${lat.toFixed(5)}, ${lng.toFixed(5)}`);
    }
  };

  const handleMapClick = (lat, lng) => {
    setTitlePin({ lat, lng });
    reverseGeocode(lat, lng);
  };

  const handleNewMapClick = async (lat, lng) => {
    setNewPin({ lat, lng });
    try {
      const res = await axios.get(
        `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`,
        { headers: { "Accept-Language": "en" } }
      );
      updateDraft("location", res.data.display_name || `${lat.toFixed(5)}, ${lng.toFixed(5)}`);
    } catch {
      updateDraft("location", `${lat.toFixed(5)}, ${lng.toFixed(5)}`);
    }
  };

  const handleSubmit = async () => {
    if (!draft.location && !newPin) { setSubmitError("Please enter a location."); return; }
    setSubmitting(true);
    setSubmitError("");
    setAnalysisResult(null);
    setDispatchData([]);
    const pinSnapshot = newPin; // capture before clearing
    setNewIncidentMode(null);
    setNewPin(null);
    try {
      const payload = {
        disaster_type: draft.predicted || "fire",
        address:       draft.location || `${pinSnapshot?.lat.toFixed(5)}, ${pinSnapshot?.lng.toFixed(5)}`,
        description:   draft.description,
      };
      if (pinSnapshot) {
        payload.latitude  = pinSnapshot.lat;
        payload.longitude = pinSnapshot.lng;
      }
      const response = await reportDisaster(payload);
      const disasterId = response.data.disaster_id;
      setAnalyzing(true);
      resetDraft();
      setView("analysis");
      pollDisasterAnalysis(disasterId, (disaster) => {
        setAnalysisResult(disaster);
        if (disaster.status === "analyzed") {
          setAnalyzing(false);
          fetchActiveDisasters();
          if (disaster.latitude && disaster.longitude) {
            setLastIncidentCoords([disaster.latitude, disaster.longitude]);
          }
          pollDispatchDecisions(disaster.id);
        }
      });
    } catch (error) {
      console.error("Failed to report incident:", error);
      setSubmitError("Failed to report incident. Is the backend running?");
    } finally {
      setSubmitting(false);
    }
  };

  const handleResolve = async () => {
    if (!resolveTarget) return;
    setResolving(true);
    try {
      await resolveDisaster(resolveTarget.id, resolutionNotes);
      setResolveTarget(null);
      setResolutionNotes("");
      fetchActiveDisasters();
    } catch { console.error("Failed to resolve incident"); }
    finally  { setResolving(false); }
  };

  const resetDraft = () => { setDraft({ location: "", description: "", predicted: "" }); setSubmitError(""); };
  const updateDraft = (field, value) => { setDraft({ ...draft, [field]: value }); setSaved(false); };
  const onEachCountry = (feature, layer) =>
    layer.on({ click: () => { setSelected(feature.properties.name); setView("country"); } });

  const stationIcon = createStationIcon();

  // ── TITLE PAGE ────────────────────────────────────────────────
  if (showTitlePage) {
    return (
      <div className="title-page">
        <div className="title-page-inner" style={{ width: titleMode === "map" ? "820px" : "370px", maxWidth: "95vw" }}>
          <h1 className="title-page-heading">
            Disaster Response<br />Planning System
          </h1>

          {/* Mode selector */}
          {!titleMode && (
            <div className="title-option-grid">
              <button
                className="title-option-card glass"
                style={{ animationDelay: "0.1s" }}
                onClick={() => setTitleMode("type")}
              >
                <span className="title-option-label">✏️ Type Location + Description</span>
              </button>
              <button
                className="title-option-card glass"
                style={{ animationDelay: "0.2s" }}
                onClick={() => setTitleMode("map")}
              >
                <span className="title-option-label">🗺️ Pick on Map + Description</span>
              </button>
              <div
                className="title-card glass title-incident-btn"
                style={{ animationDelay: "0.3s", animation: "fadeSlideIn 0.4s ease 0.3s forwards", opacity: 0 }}
                onClick={() => setShowTitlePage(false)}
              >
                View Full Incident List →
              </div>
            </div>
          )}

          {/* Type mode */}
          {titleMode === "type" && (
            <div className="title-card glass" style={{ width: "100%" }}>
              <div className="title-option-back-row">
                <button className="title-back-inline" onClick={() => { setTitleMode(null); setTitleError(""); }}>
                  ← Back
                </button>
              </div>
              <p className="title-option-selected-label">Where did the incident happen?</p>
              <label className="title-label">Location</label>
              <input
                className="title-input"
                type="text"
                placeholder="e.g. 123 W Michigan Ave, Chicago"
                value={titleLocation}
                onChange={e => setTitleLocation(e.target.value)}
              />
              <label className="title-label" style={{ marginTop: "12px" }}>Description</label>
              <textarea
                className="title-input"
                placeholder="Describe the incident…"
                rows={3}
                style={{ resize: "vertical" }}
                value={titleDesc}
                onChange={e => setTitleDesc(e.target.value)}
              />
              {titleError && <p style={{ color: "var(--red)", fontSize: "0.78rem", marginTop: "8px" }}>{titleError}</p>}
              <button className="title-enter-btn" onClick={handleTitleSubmit} disabled={titleSubmitting}>
                {titleSubmitting ? "Submitting…" : "Report Incident →"}
              </button>
            </div>
          )}

          {/* Map pick mode */}
          {titleMode === "map" && (
            <div className="title-card glass" style={{ width: "100%" }}>
              <div className="title-option-back-row">
                <button className="title-back-inline" onClick={() => { setTitleMode(null); setTitlePin(null); setTitleLocation(""); setTitleError(""); }}>
                  ← Back
                </button>
              </div>
              <p className="title-option-selected-label">Click the map to mark the incident location</p>

              {/* Inline map */}
              <div style={{ height: "320px", borderRadius: "8px", overflow: "hidden", marginBottom: "14px", border: "1px solid var(--border)" }}>
                <MapContainer center={CHICAGO_CENTER} zoom={11} style={{ height: "100%", width: "100%" }}>
                  <TileLayer url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png" attribution="© OpenStreetMap contributors © CARTO"/>
                  <MapClickHandler onMapClick={handleMapClick} />
                  {titlePin && (
                    <Marker position={[titlePin.lat, titlePin.lng]} icon={pinIcon}>
                      <Popup>{titleLocation || "Selected location"}</Popup>
                    </Marker>
                  )}
                </MapContainer>
              </div>

              <label className="title-label">Location {titlePin ? "(auto-filled from map)" : "(click map to fill)"}</label>
              <input
                className="title-input"
                type="text"
                placeholder="Click the map to auto-fill, or type manually"
                value={titleLocation}
                onChange={e => setTitleLocation(e.target.value)}
              />
              <label className="title-label" style={{ marginTop: "12px" }}>Description</label>
              <textarea
                className="title-input"
                placeholder="Describe the incident…"
                rows={3}
                style={{ resize: "vertical" }}
                value={titleDesc}
                onChange={e => setTitleDesc(e.target.value)}
              />
              {titleError && <p style={{ color: "var(--red)", fontSize: "0.78rem", marginTop: "8px" }}>{titleError}</p>}
              <button className="title-enter-btn" onClick={handleTitleSubmit} disabled={titleSubmitting}>
                {titleSubmitting ? "Submitting…" : "Report Incident →"}
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── MAIN APP ──────────────────────────────────────────────────
  return (
    <div className="app-root">
      <button className="back-btn" onClick={() => setShowTitlePage(true)}>← Home</button>

      {/* MAP */}
      <div className="map-panel glass">
        <MapContainer center={CHICAGO_CENTER} zoom={CHICAGO_ZOOM} style={{ height: "100%", width: "100%" }}>
        <TileLayer url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png" attribution="© OpenStreetMap contributors © CARTO" />
          <GeoJSON data={countriesData} onEachFeature={onEachCountry} />

          {/* Dummy station pins (Deepikka) */}
          {DUMMY_STATIONS.map(station => (
            <Marker key={station.id} position={[station.lat, station.lng]} icon={stationIcon}>
              <Tooltip direction="right" offset={[14, 0]} opacity={1} className="station-tooltip">
                <div className="station-tooltip-inner">
                  <div className="station-tooltip-name">{station.name}</div>
                  <div className="station-tooltip-divider" />
                  <div className="station-tooltip-row">
                    <span className="station-tooltip-icon">🚒</span>
                    <span className="station-tooltip-label">Fire Trucks: {station.fireTrucks}</span>
                  </div>
                  <div className="station-tooltip-row">
                    <span className="station-tooltip-icon">🚑</span>
                    <span className="station-tooltip-label">Ambulances: {station.ambulances}</span>
                  </div>
                  <div className="station-tooltip-row">
                    <span className="station-tooltip-icon">🚧</span>
                    <span className="station-tooltip-label">Other Services: {station.others}</span>
                  </div>
                </div>
              </Tooltip>
            </Marker>
          ))}

          {/* Pan to incident when analyzed */}
          {analysisResult?.latitude && analysisResult?.longitude && (
            <FlyTo coords={[analysisResult.latitude, analysisResult.longitude]} />
          )}

          {/* Incident pin — persists even after navigating away */}
          {lastIncidentCoords && (
            <Marker position={lastIncidentCoords} icon={incidentIcon}>
              <Popup>
                <b>⚠️ {analysisResult?.disaster_type?.toUpperCase() || "INCIDENT"}</b><br />
                {analysisResult?.address || ""}<br />
                {analysisResult?.priority_score ? `Priority: ${analysisResult.priority_score.toFixed(0)}` : ""}
              </Popup>
            </Marker>
          )}

          {/* Dispatch markers + routes */}
          {dispatchData.map((dispatch, i) => {
            const isFire = dispatch.dispatch_type === "fire";
            const coords = dispatch.station_coords;
            const routeCoords = dispatch.route_data?.route_coords || [];
            return coords ? (
              <span key={i}>
                <Marker position={[coords[0], coords[1]]} icon={isFire ? fireIcon : hospitalIcon}>
                  <Popup>
                    <b>{isFire ? "🚒" : "🏥"} {dispatch.station_name}</b><br />
                    {dispatch.distance_km?.toFixed(1)} km · ETA {dispatch.estimated_arrival_minutes} min
                  </Popup>
                </Marker>
                {routeCoords.length > 1 && (
                  <Polyline
                    positions={routeCoords}
                    pathOptions={{ color: isFire ? "#e63946" : "#1d7aff", weight: 4, opacity: 0.8 }}
                  />
                )}
              </span>
            ) : null;
          })}
        </MapContainer>
      </div>

      {/* RIGHT SIDE */}
      <div className="right-panel">
        <div className="menu-panel glass">
          <h1>Disaster Response Planning System</h1>
          <div className="menu-buttons">
            <button onClick={() => { setModal("incidentList"); setIncidentListPage(0); fetchActiveDisasters(); fetchResolvedDisasters(); }}>Incident Lists</button>
            <button onClick={() => setView("incidents")}>Active Incidents</button>
            <button onClick={() => setView("resolved")}>Resolved Incidents</button>
            <button onClick={() => setView("resources")}>Resources</button>
            <button onClick={() => setView("analytics")}>Analytics</button>
            <button onClick={() => setView("new")}>New Incident</button>
          </div>
        </div>

        <div className="info-panel glass">
          {view === "country" && (
            <div key="country" className="view-content">
              {selected
                ? <><h2>{selected}</h2><p style={{ color: "var(--text-dim)", fontSize: "0.82rem" }}>No active incidents for this region.</p></>
                : <p style={{ color: "var(--text-dim)", fontSize: "0.82rem" }}>Select a region on the map to view details.</p>
              }
            </div>
          )}

          {view === "incidents" && (
            <div key="incidents" className="view-content">
              <h2>Active Incidents</h2>
              {activeDisasters.length === 0
                ? <p style={{ color: "var(--text-dim)", fontSize: "0.8rem", marginTop: "8px" }}>No active incidents reported.</p>
                : activeDisasters.map((d, i) => (
                  <div key={d.id} className="incident-box"
                    style={{ display: "flex", justifyContent: "space-between", alignItems: "center", animationDelay: `${i * 0.06}s` }}>
                    <span onClick={() => setModal("severity")} style={{ cursor: "pointer", flex: 1, fontSize: "0.82rem" }}>
                      <span style={{ color: "var(--amber)", fontWeight: "bold" }}>{d.disaster_type.toUpperCase()}</span>
                      {" — "}{d.address}
                      {d.priority_score != null && (
                        <span style={{ marginLeft: "8px", color: "var(--amber-dim)", fontSize: "0.75rem" }}>
                          P:{d.priority_score.toFixed(1)}
                        </span>
                      )}
                    </span>
                    <button className="resolve-btn" onClick={() => { setResolveTarget(d); setResolutionNotes(""); }}>
                      Resolve
                    </button>
                  </div>
                ))
              }
              <div style={{ marginTop: "14px", borderTop: "1px solid var(--border)", paddingTop: "12px" }}>
                <p style={{ color: "var(--text-dim)", fontSize: "0.7rem", letterSpacing: "0.1em",
                  textTransform: "uppercase", marginBottom: "6px" }}>Incident Details</p>
                {Object.entries(INCIDENT_DETAIL_LABELS).map(([key, label], i) => (
                  <div key={key} className="incident-box" onClick={() => setModal(key)}
                    style={{ animationDelay: `${(activeDisasters.length + i) * 0.06}s` }}>
                    {label}
                  </div>
                ))}
              </div>
            </div>
          )}

          {view === "resolved" && (
            <div key="resolved" className="view-content">
              <h2>Resolved Incidents</h2>
              {resolvedDisasters.length === 0
                ? <p style={{ color: "var(--text-dim)", fontSize: "0.8rem", marginTop: "8px" }}>No resolved incidents yet.</p>
                : resolvedDisasters.map((d, i) => (
                  <div key={d.id} className="incident-box"
                    style={{ borderLeftColor: "var(--green)", animationDelay: `${i * 0.06}s` }}>
                    <strong style={{ color: "var(--green)" }}>{d.disaster_type.toUpperCase()}</strong>
                    {" — "}{d.address}<br />
                    <small style={{ color: "var(--text-dim)", fontSize: "0.72rem" }}>
                      Resolved: {d.resolved_at ? new Date(d.resolved_at).toLocaleString() : "—"}
                    </small>
                    {d.resolution_notes && (
                      <p style={{ margin: "4px 0 0", fontSize: "0.78rem", color: "var(--text-dim)" }}>
                        ↳ {d.resolution_notes}
                      </p>
                    )}
                  </div>
                ))
              }
            </div>
          )}

          {view === "new" && (
            <div key="new" className="view-content">
              <h2>New Incident</h2>

              {/* Mode selector */}
              {!newIncidentMode && (
                <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "8px" }}>
                  <button onClick={() => setNewIncidentMode("type")}
                    style={{ textAlign: "left", padding: "12px 14px" }}>
                    ✏️ Type Location + Description
                  </button>
                  <button onClick={() => setNewIncidentMode("map")}
                    style={{ textAlign: "left", padding: "12px 14px" }}>
                    🗺️ Pick on Map + Description
                  </button>
                </div>
              )}

              {/* Type mode */}
              {newIncidentMode === "type" && (
                <>
                  <button onClick={() => { setNewIncidentMode(null); resetDraft(); }}
                    style={{ fontSize: "0.7rem", marginBottom: "10px", padding: "4px 10px" }}>← Back</button>
                  <label>Location / Area</label>
                  <input value={draft.location} onChange={e => updateDraft("location", e.target.value)}
                    placeholder="e.g. 123 W Michigan Ave, Chicago" />
                  <label>Description</label>
                  <textarea value={draft.description} onChange={e => updateDraft("description", e.target.value)}
                    placeholder="Describe the incident…" rows={3} style={{ marginTop: "0", resize: "vertical" }} />
                  <label>Predicted Type</label>
                  <input value={draft.predicted} onChange={e => updateDraft("predicted", e.target.value)}
                    placeholder="fire / flood / earthquake" />
                  {submitError && <p style={{ color: "var(--red)", fontSize: "0.78rem", marginTop: "8px" }}>{submitError}</p>}
                  <div className="form-buttons">
                    <button onClick={handleSubmit} disabled={submitting}>
                      {submitting ? <><span className="submitting-indicator" />Submitting…</> : "Submit"}
                    </button>
                    <button onClick={() => { resetDraft(); setNewIncidentMode(null); setView("country"); }}>Close</button>
                  </div>
                </>
              )}

              {/* Map pick mode */}
              {newIncidentMode === "map" && (
                <>
                  <button onClick={() => { setNewIncidentMode(null); setNewPin(null); resetDraft(); }}
                    style={{ fontSize: "0.7rem", marginBottom: "8px", padding: "4px 10px" }}>← Back</button>
                  <p style={{ color: "var(--text-dim)", fontSize: "0.75rem", marginBottom: "8px" }}>
                    Click the map to mark the incident location
                  </p>
                  <div style={{ height: "200px", borderRadius: "8px", overflow: "hidden", marginBottom: "10px", border: "1px solid var(--border)" }}>
                    <MapContainer center={CHICAGO_CENTER} zoom={11} style={{ height: "100%", width: "100%" }}>
                    <TileLayer url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png" attribution="© OpenStreetMap contributors © CARTO" />
                      <MapClickHandler onMapClick={handleNewMapClick} />
                      {newPin && (
                        <Marker position={[newPin.lat, newPin.lng]} icon={pinIcon}>
                          <Popup>{draft.location || "Selected location"}</Popup>
                        </Marker>
                      )}
                    </MapContainer>
                  </div>
                  <label>Location {newPin ? "(auto-filled)" : "(click map)"}</label>
                  <input value={draft.location} onChange={e => updateDraft("location", e.target.value)}
                    placeholder="Click map to auto-fill, or type manually" />
                  <label>Description</label>
                  <textarea value={draft.description} onChange={e => updateDraft("description", e.target.value)}
                    placeholder="Describe the incident…" rows={2} style={{ marginTop: "0", resize: "vertical" }} />
                  <label>Predicted Type</label>
                  <input value={draft.predicted} onChange={e => updateDraft("predicted", e.target.value)}
                    placeholder="fire / flood / earthquake" />
                  {submitError && <p style={{ color: "var(--red)", fontSize: "0.78rem", marginTop: "8px" }}>{submitError}</p>}
                  <div className="form-buttons">
                    <button onClick={handleSubmit} disabled={submitting}>
                      {submitting ? <><span className="submitting-indicator" />Submitting…</> : "Submit"}
                    </button>
                    <button onClick={() => { resetDraft(); setNewIncidentMode(null); setNewPin(null); setView("country"); }}>Close</button>
                  </div>
                </>
              )}
            </div>
          )}

          {view === "analysis" && (
            <div key="analysis" className="view-content">
              <h2>Incident Analysis</h2>
              {analyzing && (
                <p style={{ color: "var(--text-dim)", fontSize: "0.8rem", marginTop: "8px" }}>
                  <span className="submitting-indicator" />Analyzing incident…
                </p>
              )}
              {analysisResult && (
                <div>
                  {[
                    ["Type",                analysisResult.disaster_type],
                    ["Address",             analysisResult.address],
                    ["Confidence Score",    analysisResult.confidence_score ? `${analysisResult.confidence_score.toFixed(1)}%` : "Analyzing…"],
                    ["Severity Score",      analysisResult.severity_score   || "Analyzing…"],
                    ["Population Affected", analysisResult.population_affected ? analysisResult.population_affected.toLocaleString() : "Analyzing…"],
                    ["Latitude",            analysisResult.latitude   || "Analyzing…"],
                    ["Longitude",           analysisResult.longitude  || "Analyzing…"],
                    ["Status",              analysisResult.status],
                    ["Priority Score",      analysisResult.priority_score != null ? analysisResult.priority_score.toFixed(1) : ""],
                  ].map(([lbl, val]) => (
                    <div className="row" key={lbl}>
                      <label style={{ margin: 0 }}>{lbl}</label>
                      <input readOnly value={val || ""} />
                    </div>
                  ))}

                  {/* ── Dispatch strip ── */}
                  {dispatchData.length > 0 && (
                    <div style={{
                      marginTop: "14px", padding: "12px 14px",
                      background: "rgba(0,0,0,0.3)", border: "1px solid var(--border)",
                      borderRadius: "6px",
                    }}>
                      <div style={{
                        fontSize: "0.65rem", letterSpacing: "0.12em",
                        textTransform: "uppercase", color: "var(--text-label)",
                        marginBottom: "8px",
                      }}>Units Dispatched</div>
                      {dispatchData.map((dispatch, i) => {
                        const isFire = dispatch.dispatch_type === "fire";
                        const name = dispatch.station_name || "—";
                        return (
                          <div key={i} style={{
                            display: "flex", alignItems: "center", gap: "10px",
                            padding: "8px 0",
                            borderTop: i > 0 ? "1px solid var(--border)" : "none",
                            fontSize: "0.78rem",
                          }}>
                            <span style={{ fontSize: "1.1rem" }}>{isFire ? "🚒" : "🚑"}</span>
                            <span style={{ flex: 1, color: "var(--text)" }}>{name}</span>
                            <span style={{ color: "var(--text-dim)", whiteSpace: "nowrap" }}>
                              {dispatch.distance_km?.toFixed(1)} km
                            </span>
                            <span style={{
                              color: isFire ? "var(--red)" : "var(--amber)",
                              whiteSpace: "nowrap", fontWeight: "bold",
                            }}>
                              ETA {dispatch.estimated_arrival_minutes} min
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {analysisResult.status === "analyzed" && dispatchData.length === 0 && (
                    <p style={{ color: "var(--text-dim)", fontSize: "0.78rem", marginTop: "10px" }}>
                      <span className="submitting-indicator" />Routing dispatch…
                    </p>
                  )}
                  {analysisResult.status === "analyzed" && dispatchData.length > 0 && (
                    <p style={{ color: "var(--green)", fontSize: "0.78rem", marginTop: "10px" }}>
                      ✓ Analysis complete
                    </p>
                  )}
                </div>
              )}
              <div className="form-buttons">
                <button onClick={() => setView("incidents")}>View All Incidents</button>
                <button onClick={() => setView("new")}>Report Another</button>
              </div>
            </div>
          )}

          {view === "analytics" && (
            <div key="analytics" className="view-content">
              <h2>Analytics</h2>
              {[
                ["Active Incidents",   analyticsData ? analyticsData.incidents.active   : activeDisasters.length],
                ["Resolved Incidents", analyticsData ? analyticsData.incidents.resolved : "—"],
                ["Total Incidents",    analyticsData ? analyticsData.incidents.total    : "—"],
                ["Avg Response Time",  analyticsData ? `${analyticsData.avg_response_time_minutes} min` : "—"],
                ["AI Confidence",      analyticsData ? `${analyticsData.avg_confidence_pct}%` : "—"],
                ["Avg Severity Score", analyticsData ? analyticsData.avg_severity : "—"],
              ].map(([lbl, val]) => (
                <div className="row" key={lbl}>
                  <label style={{ margin: 0 }}>{lbl}</label>
                  <input value={val} readOnly onChange={() => {}} />
                </div>
              ))}
              <div className="resources-subbox">
                <h3 style={{ fontFamily: "var(--font-display)", fontSize: "0.85rem",
                  letterSpacing: "0.08em", textTransform: "uppercase",
                  color: "var(--amber-dim)", marginBottom: "12px" }}>Dispatch Summary</h3>
                {[
                  ["Fire Dispatches",      analyticsData ? analyticsData.dispatches.fire      : "—"],
                  ["Ambulance Dispatches", analyticsData ? analyticsData.dispatches.ambulance  : "—"],
                  ["Total Dispatches",     analyticsData ? analyticsData.dispatches.total      : "—"],
                ].map(([lbl, val]) => (
                  <div className="row" key={lbl}>
                    <label style={{ margin: 0 }}>{lbl}</label>
                    <input value={val} readOnly onChange={() => {}} />
                  </div>
                ))}
              </div>
              <div className="resources-subbox">
                <h3 style={{ fontFamily: "var(--font-display)", fontSize: "0.85rem",
                  letterSpacing: "0.08em", textTransform: "uppercase",
                  color: "var(--amber-dim)", marginBottom: "12px" }}>Incident Types</h3>
                {analyticsData ? analyticsData.type_breakdown.map(({ disaster_type, count }) => (
                  <div className="row" key={disaster_type}>
                    <label style={{ margin: 0 }}>{disaster_type.toUpperCase()}</label>
                    <input value={count} readOnly onChange={() => {}} />
                  </div>
                )) : (
                  <p style={{ color: "var(--text-dim)", fontSize: "0.78rem" }}>Loading…</p>
                )}
              </div>
            </div>
          )}

          {view === "resources" && (
            <div key="resources" className="view-content">
              <h2>Resources</h2>
              <div className="resource-top-buttons">
                {Object.entries(RESOURCE_ICONS).map(([name, icon]) => (
                  <button key={name} onClick={() => setResourceModal(name)}>{icon} {name}</button>
                ))}
              </div>
              <div className="glass resource-card">
                <h3 style={{ fontFamily: "var(--font-display)", fontSize: "0.85rem",
                  letterSpacing: "0.08em", textTransform: "uppercase",
                  color: "var(--amber-dim)", marginBottom: "12px" }}>All Resources</h3>
                {[
                  ["Fire Trucks Availability",  fireStations.reduce((s, x) => s + x.available_trucks, 0)],
                  ["Ambulance Availability",    hospitals.reduce((s, x) => s + x.available_ambulances, 0)],
                  ["Police Units Availability", "N/A"],
                  ["Other Availability",        "N/A"],
                  ["Total Availability",        fireStations.reduce((s, x) => s + x.available_trucks, 0) + hospitals.reduce((s, x) => s + x.available_ambulances, 0)],
                ].map(([lbl, val]) => (
                  <div className="resource-row" key={lbl}>
                    <label>{lbl}</label>
                    <input value={val} readOnly onChange={() => {}} />
                  </div>
                ))}
                <div className="resource-actions">
                  <button>Assign</button>
                  <button>Reserve</button>
                  <button>Disable</button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── RESOLVE MODAL ── */}
      {resolveTarget && (
        <div className="modal-overlay">
          <div className="modal glass">
            <h2>Resolve Incident</h2>
            <p style={{ color: "var(--text-dim)", fontSize: "0.82rem", marginBottom: "14px" }}>
              <span style={{ color: "var(--amber)" }}>{resolveTarget.disaster_type.toUpperCase()}</span>
              {" — "}{resolveTarget.address}
            </p>
            <label>Resolution Notes</label>
            <textarea value={resolutionNotes} onChange={e => setResolutionNotes(e.target.value)}
              placeholder="e.g. Fire extinguished by Engine 42, no casualties"
              rows={4} style={{ resize: "vertical" }} />
            <div className="modal-buttons">
              <button onClick={() => { setResolveTarget(null); setResolutionNotes(""); }}>Cancel</button>
              <button onClick={handleResolve} disabled={resolving}
                style={{ background: "rgba(62,207,114,0.1)", borderColor: "rgba(62,207,114,0.3)", color: "var(--green)" }}>
                {resolving ? "Resolving…" : "Confirm Resolved"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── RESOURCE DETAIL POPUP ── */}
      {resourceModal && (
        <div className="modal-overlay" onClick={() => setResourceModal(null)}>
          <div className="modal glass resource-popup" onClick={e => e.stopPropagation()}>
            <div className="resource-popup-header">
              <span className="resource-popup-icon">{RESOURCE_ICONS[resourceModal]}</span>
              <h2>{resourceModal}</h2>
            </div>
            {[
              ["Total Availability",      "total"],
              ["Nearest Within 100m",     "nearestWithin100m"],
              ["Estimated Response Time", "estimatedResponseTime"],
            ].map(([lbl, field]) => (
              <div className="resource-detail-row" key={field}>
                <label>{lbl}</label>
                <input value={resourceFields[resourceModal][field]}
                  onChange={e => updateResourceField(resourceModal, field, e.target.value)} />
              </div>
            ))}
            <div className="modal-buttons">
              <button onClick={() => setResourceModal(null)}>Close</button>
              <button onClick={() => { alert("Saved!"); setResourceModal(null); }}>Save</button>
            </div>
          </div>
        </div>
      )}

      {/* ── INCIDENT LIST FULL PAGE OVERLAY ── */}
      {modal === "incidentList" && (() => {
        const allIncidents = [...activeDisasters, ...resolvedDisasters]
          .sort((a, b) => new Date(b.reported_at) - new Date(a.reported_at));
        const totalPages = Math.ceil(allIncidents.length / INCIDENTS_PER_PAGE);
        const pageItems = allIncidents.slice(
          incidentListPage * INCIDENTS_PER_PAGE,
          (incidentListPage + 1) * INCIDENTS_PER_PAGE
        );
        return (
          <div style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)",
            backdropFilter: "blur(8px)", zIndex: 999,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <div style={{
              width: "680px", maxWidth: "92vw", maxHeight: "88vh",
              background: "var(--bg-panel)", border: "1px solid var(--border)",
              borderRadius: "12px", display: "flex", flexDirection: "column",
              boxShadow: "0 0 0 1px rgba(0,0,0,0.4), 0 8px 32px rgba(0,0,0,0.6)",
            }}>
              {/* Header */}
              <div style={{
                padding: "20px 24px 14px", borderBottom: "1px solid var(--border)",
                display: "flex", justifyContent: "space-between", alignItems: "center",
              }}>
                <h2 style={{ fontFamily: "var(--font-display)", fontSize: "0.95rem",
                  letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--amber)", margin: 0 }}>
                  ▸ Full Incident List
                </h2>
                <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                  <span style={{ color: "var(--text-dim)", fontSize: "0.72rem" }}>
                    {allIncidents.length} total
                  </span>
                  <button onClick={() => setModal(null)} style={{
                    padding: "5px 14px", fontSize: "0.7rem", background: "rgba(224,82,82,0.1)",
                    borderColor: "rgba(224,82,82,0.3)", color: "var(--red)",
                  }}>✕ Close</button>
                </div>
              </div>

              {/* Incident rows */}
              <div style={{ flex: 1, overflowY: "auto", padding: "12px 24px" }}>
                {allIncidents.length === 0
                  ? <p style={{ color: "var(--text-dim)", fontSize: "0.8rem", marginTop: "16px" }}>No incidents reported yet.</p>
                  : pageItems.map((d, i) => (
                    <div key={d.id} style={{
                      border: "1px solid var(--border)",
                      borderLeft: `3px solid ${d.status === "resolved" ? "var(--green)" : "var(--amber-dim)"}`,
                      padding: "12px 14px", marginBottom: "8px", borderRadius: "6px",
                      fontSize: "0.82rem",
                    }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                        <div>
                          <strong style={{ color: d.status === "resolved" ? "var(--green)" : "var(--amber)" }}>
                            {d.disaster_type.toUpperCase()}
                          </strong>
                          {" — "}
                          <span style={{ color: "var(--text)" }}>{d.address}</span>
                        </div>
                        <span style={{
                          fontSize: "0.68rem", padding: "2px 8px", borderRadius: "4px",
                          background: d.status === "resolved" ? "rgba(62,207,114,0.1)" : "rgba(255,180,50,0.1)",
                          color: d.status === "resolved" ? "var(--green)" : "var(--amber)",
                          border: `1px solid ${d.status === "resolved" ? "rgba(62,207,114,0.25)" : "rgba(255,180,50,0.25)"}`,
                          whiteSpace: "nowrap", marginLeft: "10px",
                        }}>
                          {d.status}
                        </span>
                      </div>
                      <div style={{ marginTop: "4px", color: "var(--text-dim)", fontSize: "0.72rem", display: "flex", gap: "16px" }}>
                        <span>{new Date(d.reported_at).toLocaleString()}</span>
                        {d.priority_score > 0 && <span>Priority: {d.priority_score.toFixed(0)}</span>}
                        {d.severity_score > 0 && <span>Severity: {d.severity_score}</span>}
                      </div>
                    </div>
                  ))
                }
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div style={{
                  padding: "14px 24px", borderTop: "1px solid var(--border)",
                  display: "flex", justifyContent: "center", alignItems: "center", gap: "8px",
                }}>
                  <button onClick={() => setIncidentListPage(p => Math.max(0, p - 1))}
                    disabled={incidentListPage === 0}
                    style={{ padding: "5px 14px", opacity: incidentListPage === 0 ? 0.4 : 1 }}>
                    ← Prev
                  </button>
                  {Array.from({ length: totalPages }, (_, i) => (
                    <button key={i} onClick={() => setIncidentListPage(i)}
                      style={{
                        padding: "5px 10px", minWidth: "32px",
                        background: i === incidentListPage ? "rgba(80,160,255,0.2)" : "rgba(255,180,50,0.05)",
                        borderColor: i === incidentListPage ? "var(--amber)" : "var(--border)",
                        color: i === incidentListPage ? "var(--amber)" : "var(--text-dim)",
                      }}>
                      {i + 1}
                    </button>
                  ))}
                  <button onClick={() => setIncidentListPage(p => Math.min(totalPages - 1, p + 1))}
                    disabled={incidentListPage === totalPages - 1}
                    style={{ padding: "5px 14px", opacity: incidentListPage === totalPages - 1 ? 0.4 : 1 }}>
                    Next →
                  </button>
                </div>
              )}
            </div>
          </div>
        );
      })()}


      {/* ── OTHER MODALS ── */}
      {modal && modal !== "incidentList" && (
        <div className="modal-overlay">
          <div className="modal glass">
            {modal === "severity" && (
              <>
                <h2>Severity Scaling</h2>
                <label>Input</label>
                <input value={severityInput} onChange={e => setSeverityInput(e.target.value)} />
                <label>Severity Score</label>
                <input value={severityScore} onChange={e => setSeverityScore(e.target.value)} />
                <label>Notes — Keywords Found</label>
                <textarea value={severityNotes} onChange={e => setSeverityNotes(e.target.value)} rows={3} style={{ resize: "vertical" }} />
              </>
            )}
            {modal === "population" && (
              <>
                <h2>Population / Exposure</h2>
                {[["Area Size","area"],["Buildings in Area","buildings"],["Dominant Building","type"],["Estimated People","people"]].map(([lbl,k]) => (
                  <div className="row" key={k}>
                    <label style={{ margin: 0 }}>{lbl}</label>
                    <input value={populationData[k]} onChange={e => setPopulationData({ ...populationData, [k]: e.target.value })} />
                  </div>
                ))}
              </>
            )}
            {modal === "routing" && (
              <>
                <h2>Routing & Travel Time</h2>
                {[["Nearest Station","station"],["ETA (Current)","eta"],["Traffic","traffic"],["Closures / Blocks","blocks"]].map(([lbl,k]) => (
                  <div className="row" key={k}>
                    <label style={{ margin: 0 }}>{lbl}</label>
                    <input value={routingData[k]} onChange={e => setRoutingData({ ...routingData, [k]: e.target.value })} />
                  </div>
                ))}
              </>
            )}
            {modal === "feasibility" && (
              <><h2>Feasibility Score</h2>
              <label>Score</label>
              <input value={feasibilityData} onChange={e => setFeasibilityData(e.target.value)} placeholder="0–100" /></>
            )}
            {modal === "ambulances" && (
              <><h2>Ambulances Ready?</h2>
              <label>Status</label>
              <input value={ambulanceData} onChange={e => setAmbulanceData(e.target.value)} placeholder="e.g. 4 available" /></>
            )}
            {modal === "weather" && (
              <><h2>Weather Constraints</h2>
              <label>Conditions</label>
              <input value={weatherData} onChange={e => setWeatherData(e.target.value)} placeholder="e.g. 25 mph wind, light rain" /></>
            )}
            <div className="modal-buttons">
              <button onClick={() => setModal(null)}>Close</button>
              <button onClick={() => { alert("Saved!"); setModal(null); }}>Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}