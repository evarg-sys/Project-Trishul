import { MapContainer, TileLayer, GeoJSON } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { useState, useEffect } from "react";
import "./App.css";
import countriesData from "./data/countries.json";
import { reportDisaster, getActiveDisasters, getFireStations, pollDisasterAnalysis, resolveDisaster } from "./services/api";
import axios from "axios";

const API_BASE_URL = "http://localhost:8000/api";

const RESOURCE_ICONS = {
  "Fire Trucks": "🚒",
  Ambulances:    "🚑",
  "Police Units":"🚓",
  Others:        "🚧",
};

const CHICAGO_CENTER = [41.8781, -87.6298];
const CHICAGO_ZOOM   = 10;

// Label map for incident detail boxes
const INCIDENT_DETAIL_LABELS = {
  severity:    "Severity Score",
  population:  "Population / Exposure",
  routing:     "Routing & Travel Time",
  feasibility: "Feasibility Score",
  ambulances:  "Ambulances Ready?",
  weather:     "Weather Constraints?",
};

export default function App() {
  // ── Title page ────────────────────────────────────────────────
  const [showTitlePage, setShowTitlePage] = useState(true);
  const [titleLocation, setTitleLocation] = useState("");
  const [titleZipCode,  setTitleZipCode]  = useState("");

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

  useEffect(() => {
    if (view === "incidents") fetchActiveDisasters();
    if (view === "resolved")  fetchResolvedDisasters();
  }, [view]);

  useEffect(() => { fetchFireStations(); }, []);

  const fetchActiveDisasters = async () => {
    try   { const r = await getActiveDisasters();                          setActiveDisasters(r.data); }
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

  const handleSubmit = async () => {
    if (!draft.location) { setSubmitError("Please enter a location."); return; }
    setSubmitting(true);
    setSubmitError("");
    setAnalysisResult(null);
    try {
      const response = await reportDisaster({
        disaster_type: draft.predicted || "fire",
        address:       draft.location,
        description:   draft.description,
      });
      const disasterId = response.data.disaster_id;
      setAnalyzing(true);
      resetDraft();
      setView("analysis");
      pollDisasterAnalysis(disasterId, (disaster) => {
        setAnalysisResult(disaster);
        if (disaster.status === "analyzed") { setAnalyzing(false); fetchActiveDisasters(); }
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

  // ── TITLE PAGE ────────────────────────────────────────────────
  if (showTitlePage) {
    return (
      <div className="title-page">
        <div className="title-page-inner">
          <h1 className="title-page-heading">
            Disaster Response<br />Planning System
          </h1>

          <div className="title-card glass">
            <label className="title-label">Location</label>
            <input className="title-input" type="text" placeholder="Enter location"
              value={titleLocation} onChange={e => setTitleLocation(e.target.value)} />
            <label className="title-label">Zip Code</label>
            <input className="title-input" type="text" placeholder="Enter zip code"
              value={titleZipCode} onChange={e => setTitleZipCode(e.target.value)} />
          </div>

          <div className="title-card glass title-incident-btn" onClick={() => setShowTitlePage(false)}>
            View Full Incident List →
          </div>
        </div>
      </div>
    );
  }

  // ── MAIN APP ──────────────────────────────────────────────────
  return (
    <div className="app-root">
      <button className="back-btn" onClick={() => setShowTitlePage(true)}>← Back</button>

      {/* MAP */}
      <div className="map-panel glass">
        <MapContainer center={CHICAGO_CENTER} zoom={CHICAGO_ZOOM} style={{ height: "100%", width: "100%" }}>
          <TileLayer url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png" subdomains="abcd" />
          <GeoJSON data={countriesData} onEachFeature={onEachCountry} />
        </MapContainer>
      </div>

      {/* RIGHT SIDE */}
      <div className="right-panel">
        <div className="menu-panel glass">
          <h1>Disaster Response Planning System</h1>
          <div className="menu-buttons">
            <button onClick={() => setModal("incidentList")}>Incident Lists</button>
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
                    <button className="resolve-btn"
                      onClick={() => { setResolveTarget(d); setResolutionNotes(""); }}>
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
                    {" — "}{d.address}
                    <br />
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
                <button onClick={() => { if (!saved) resetDraft(); setSaved(false); setView("country"); }}>Close</button>
                <button onClick={() => { setSaved(true); alert("Draft saved."); }}>Save Draft</button>
              </div>
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
                    ["Type",               analysisResult.disaster_type],
                    ["Address",            analysisResult.address],
                    ["Confidence Score",   analysisResult.confidence_score ? `${analysisResult.confidence_score.toFixed(1)}%` : "Analyzing…"],
                    ["Severity Score",     analysisResult.severity_score   || "Analyzing…"],
                    ["Population Affected",analysisResult.population_affected ? analysisResult.population_affected.toLocaleString() : "Analyzing…"],
                    ["Latitude",           analysisResult.latitude   || "Analyzing…"],
                    ["Longitude",          analysisResult.longitude  || "Analyzing…"],
                    ["Status",             analysisResult.status],
                    ["Priority Score",     analysisResult.priority_score != null ? analysisResult.priority_score.toFixed(1) : ""],
                  ].map(([lbl, val]) => (
                    <div className="row" key={lbl}>
                      <label style={{ margin: 0 }}>{lbl}</label>
                      <input readOnly value={val || ""} />
                    </div>
                  ))}
                  {analysisResult.status === "analyzed" && (
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
                ["Average Response Time", ""],
                ["AI Accuracy",           ""],
                ["Active Incidents",      activeDisasters.length],
                ["Average Severity",      ""],
              ].map(([lbl, val]) => (
                <div className="row" key={lbl}>
                  <label style={{ margin: 0 }}>{lbl}</label>
                  <input value={val} readOnly={lbl === "Active Incidents"} onChange={() => {}} />
                </div>
              ))}
              <div className="resources-subbox">
                <h3 style={{ fontFamily: "var(--font-display)", fontSize: "0.85rem",
                  letterSpacing: "0.08em", textTransform: "uppercase",
                  color: "var(--amber-dim)", marginBottom: "12px" }}>Resource Utilization</h3>
                {["Fire Truck","Ambulance","Police Units"].map(r => (
                  <div className="row" key={r}>
                    <label style={{ margin: 0 }}>{r} Utilization</label>
                    <input />
                  </div>
                ))}
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
                  ["Ambulance Availability",    ""],
                  ["Police Units Availability", ""],
                  ["Other Availability",        ""],
                  ["Total Availability",        ""],
                ].map(([lbl, val]) => (
                  <div className="resource-row" key={lbl}>
                    <label>{lbl}</label>
                    <input value={val} readOnly={lbl === "Fire Trucks Availability"} onChange={() => {}} />
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

      {/* ── RESOLVE MODAL ──────────────────────────────────────── */}
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

      {/* ── RESOURCE DETAIL POPUP ──────────────────────────────── */}
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

      {/* ── OTHER MODALS ───────────────────────────────────────── */}
      {modal && (
        <div className="modal-overlay">
          <div className="modal glass">

            {modal === "incidentList" && (
              <>
                <h2>Full Incident List</h2>
                {activeDisasters.length === 0
                  ? <p style={{ color: "var(--text-dim)", fontSize: "0.8rem" }}>No incidents reported yet.</p>
                  : activeDisasters.map((d, i) => (
                    <div key={d.id} className="incident-box" style={{ animationDelay: `${i * 0.06}s` }}>
                      <strong style={{ color: "var(--amber)" }}>{d.disaster_type.toUpperCase()}</strong>
                      {" — "}{d.address}<br />
                      <small style={{ color: "var(--text-dim)", fontSize: "0.72rem" }}>
                        Status: {d.status} · {new Date(d.reported_at).toLocaleString()}
                      </small>
                    </div>
                  ))
                }
              </>
            )}

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