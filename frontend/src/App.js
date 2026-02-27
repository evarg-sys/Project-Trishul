import { MapContainer, TileLayer, GeoJSON } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { useState, useEffect } from "react";
import "./App.css";
import countriesData from "./data/countries.json";
import { reportDisaster, getActiveDisasters, getFireStations } from "./services/api";

export default function App() {
  const [selected, setSelected] = useState(null);
  const [view, setView] = useState("country");
  const [modal, setModal] = useState(null);

  const [saved, setSaved] = useState(false);
  const [draft, setDraft] = useState({
    location: "",
    description: "",
    predicted: "",
    confidence: "",
    keywords: "",
  });

  const [severityInput, setSeverityInput] = useState("");
  const [severityScore, setSeverityScore] = useState("");
  const [severityNotes, setSeverityNotes] = useState("");

  const [populationData, setPopulationData] = useState({
    area: "",
    buildings: "",
    type: "",
    people: "",
  });

  const [routingData, setRoutingData] = useState({
    station: "",
    eta: "",
    traffic: "",
    blocks: "",
  });

  const [feasibilityData, setFeasibilityData] = useState("");
  const [ambulanceData, setAmbulanceData] = useState("");
  const [weatherData, setWeatherData] = useState("");

  // Backend state
  const [activeDisasters, setActiveDisasters] = useState([]);
  const [fireStations, setFireStations] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  // Load active disasters when switching to incidents view
  useEffect(() => {
    if (view === "incidents") {
      fetchActiveDisasters();
    }
  }, [view]);

  // Load fire stations on mount
  useEffect(() => {
    fetchFireStations();
  }, []);

  const fetchActiveDisasters = async () => {
    try {
      const response = await getActiveDisasters();
      setActiveDisasters(response.data);
    } catch (error) {
      console.error("Failed to fetch active disasters:", error);
    }
  };

  const fetchFireStations = async () => {
    try {
      const response = await getFireStations();
      setFireStations(response.data);
    } catch (error) {
      console.error("Failed to fetch fire stations:", error);
    }
  };

  const handleSubmit = async () => {
    if (!draft.location) {
      setSubmitError("Please enter a location.");
      return;
    }

    setSubmitting(true);
    setSubmitError("");

    try {
      await reportDisaster({
        disaster_type: draft.predicted || "fire",
        address: draft.location,
        description: draft.description,
      });
      alert("Incident reported successfully!");
      resetDraft();
      setSaved(false);
      setView("country");
    } catch (error) {
      console.error("Failed to report incident:", error);
      setSubmitError("Failed to report incident. Is the backend running?");
    } finally {
      setSubmitting(false);
    }
  };

  const resetDraft = () => {
    setDraft({
      location: "",
      description: "",
      predicted: "",
      confidence: "",
      keywords: "",
    });
    setSubmitError("");
  };

  const updateDraft = (field, value) => {
    setDraft({ ...draft, [field]: value });
    setSaved(false);
  };

  const onEachCountry = (feature, layer) => {
    layer.on({
      click: () => {
        setSelected(feature.properties.name);
        setView("country");
      },
    });
  };

  return (
    <div className="app-root">
      {/* MAP */}
      <div className="map-panel glass">
        <MapContainer center={[20, 0]} zoom={2} style={{ height: "100%", width: "100%" }}>
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
            subdomains="abcd"
          />
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
            <button onClick={() => setView("resources")}>Resources</button>
            <button onClick={() => setView("analytics")}>Analytics</button>
            <button onClick={() => setView("new")}>New Incident</button>
          </div>
        </div>

        <div className="info-panel glass">
          {view === "country" &&
            (selected ? (
              <>
                <h2>{selected}</h2>
                <p>Description will go here later</p>
              </>
            ) : (
              <p>Click a country</p>
            ))}

          {view === "incidents" && (
            <>
              <h2>Active Incidents</h2>
              {activeDisasters.length === 0 ? (
                <p style={{ color: "#aaa", marginTop: "10px" }}>No active incidents reported.</p>
              ) : (
                activeDisasters.map((disaster) => (
                  <div
                    key={disaster.id}
                    className="incident-box"
                    onClick={() => setModal("severity")}
                  >
                    {disaster.disaster_type.toUpperCase()} — {disaster.address}
                  </div>
                ))
              )}
              <div style={{ marginTop: "15px" }}>
                <div className="incident-box" onClick={() => setModal("severity")}>Severity Score</div>
                <div className="incident-box" onClick={() => setModal("population")}>Population / Exposure</div>
                <div className="incident-box" onClick={() => setModal("routing")}>Routing & Travel Time</div>
                <div className="incident-box" onClick={() => setModal("feasibility")}>Feasibility Score</div>
                <div className="incident-box" onClick={() => setModal("ambulances")}>Ambulances Ready?</div>
                <div className="incident-box" onClick={() => setModal("weather")}>Weather Constraints?</div>
              </div>
            </>
          )}

          {view === "new" && (
            <div className="form-box">
              <h2>New Incident</h2>
              <label>Location / Area</label>
              <input value={draft.location} onChange={e => updateDraft("location", e.target.value)} />
              <label>Description</label>
              <textarea value={draft.description} onChange={e => updateDraft("description", e.target.value)} />
              <label>Predicted Type</label>
              <input value={draft.predicted} onChange={e => updateDraft("predicted", e.target.value)} placeholder="fire / flood / earthquake" />
              <label>Confidence</label>
              <input value={draft.confidence} onChange={e => updateDraft("confidence", e.target.value)} />
              <label>Keywords Found</label>
              <input value={draft.keywords} onChange={e => updateDraft("keywords", e.target.value)} />

              {submitError && (
                <p style={{ color: "red", marginTop: "8px" }}>{submitError}</p>
              )}

              <div className="form-buttons">
                <button onClick={handleSubmit} disabled={submitting}>
                  {submitting ? "Submitting..." : "Submit"}
                </button>
                <button onClick={() => { if (!saved) resetDraft(); setSaved(false); setView("country"); }}>Close</button>
                <button onClick={() => { setSaved(true); alert("Draft saved successfully!"); }}>Save Draft</button>
              </div>
            </div>
          )}

          {view === "analytics" && (
            <div className="analytics-box">
              <h2>Analytics</h2>
              <div className="row"><label>Average Response Time:</label><input /></div>
              <div className="row"><label>AI Accuracy:</label><input /></div>
              <div className="row"><label>Active Incidents:</label><input value={activeDisasters.length} readOnly /></div>
              <div className="row"><label>Average Severity:</label><input /></div>
              <div className="resources-subbox">
                <h3>Resources</h3>
                <div className="row"><label>Fire Truck Utilization:</label><input /></div>
                <div className="row"><label>Ambulance Utilization:</label><input /></div>
                <div className="row"><label>Police Units Utilization:</label><input /></div>
              </div>
            </div>
          )}

          {view === "resources" && (
            <div className="resources-clean">
              <h2>Resources</h2>

              <div className="resource-top-buttons">
                <button>Fire Trucks</button>
                <button>Ambulances</button>
                <button>Police Units</button>
                <button>Others</button>
              </div>

              <div className="glass resource-card">
                <h3>All Resources</h3>

                <div className="resource-row">
                  <label>Fire Trucks Availability</label>
                  <input value={fireStations.reduce((sum, s) => sum + s.available_trucks, 0)} readOnly />
                </div>

                <div className="resource-row">
                  <label>Ambulance Availability</label>
                  <input />
                </div>

                <div className="resource-row">
                  <label>Police Units Availability</label>
                  <input />
                </div>

                <div className="resource-row">
                  <label>Other Availability</label>
                  <input />
                </div>

                <div className="resource-row">
                  <label>Total Availability</label>
                  <input />
                </div>

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

      {/* MODALS */}
      {modal && (
        <div className="modal-overlay">
          <div className="modal glass">
            {modal === "incidentList" && (
              <div>
                <h2>Full Incident List</h2>
                {activeDisasters.length === 0 ? (
                  <p style={{ color: "#aaa", marginTop: "10px" }}>No incidents reported yet.</p>
                ) : (
                  activeDisasters.map((disaster) => (
                    <div key={disaster.id} className="incident-box">
                      <strong>{disaster.disaster_type.toUpperCase()}</strong> — {disaster.address}
                      <br />
                      <small>Status: {disaster.status} | Reported: {new Date(disaster.reported_at).toLocaleString()}</small>
                    </div>
                  ))
                )}
              </div>
            )}

            {modal === "severity" && (
              <div className="form-box">
                <h2>Severity Scaling</h2>
                <label>Input:</label>
                <input value={severityInput} onChange={e => setSeverityInput(e.target.value)} />
                <label>Severity Score:</label>
                <input value={severityScore} onChange={e => setSeverityScore(e.target.value)} />
                <label>Notes (Keywords Found):</label>
                <textarea value={severityNotes} onChange={e => setSeverityNotes(e.target.value)} />
              </div>
            )}

            {modal === "population" && (
              <div className="population-box">
                <h2>Population / Exposure</h2>
                <div className="row"><label>Area Size:</label><input value={populationData.area} onChange={e => setPopulationData({ ...populationData, area: e.target.value })} /></div>
                <div className="row"><label>Buildings in Area:</label><input value={populationData.buildings} onChange={e => setPopulationData({ ...populationData, buildings: e.target.value })} /></div>
                <div className="row"><label>Dominant Building:</label><input value={populationData.type} onChange={e => setPopulationData({ ...populationData, type: e.target.value })} /></div>
                <div className="row"><label>Estimated People:</label><input value={populationData.people} onChange={e => setPopulationData({ ...populationData, people: e.target.value })} /></div>
              </div>
            )}

            {modal === "routing" && (
              <div className="routing-box">
                <h2>Routing and Travel Time</h2>
                <div className="row"><label>Nearest Station:</label><input value={routingData.station} onChange={e => setRoutingData({ ...routingData, station: e.target.value })} /></div>
                <div className="row"><label>ETA (current):</label><input value={routingData.eta} onChange={e => setRoutingData({ ...routingData, eta: e.target.value })} /></div>
                <div className="row"><label>Traffic:</label><input value={routingData.traffic} onChange={e => setRoutingData({ ...routingData, traffic: e.target.value })} /></div>
                <div className="row"><label>Closures/Blocks:</label><input value={routingData.blocks} onChange={e => setRoutingData({ ...routingData, blocks: e.target.value })} /></div>
              </div>
            )}

            {modal === "feasibility" && (
              <div className="form-box">
                <h2>Feasibility Score</h2>
                <input value={feasibilityData} onChange={e => setFeasibilityData(e.target.value)} placeholder="Feasibility score" />
              </div>
            )}

            {modal === "ambulances" && (
              <div className="form-box">
                <h2>Ambulances Ready?</h2>
                <input value={ambulanceData} onChange={e => setAmbulanceData(e.target.value)} placeholder="Ambulances ready?" />
              </div>
            )}

            {modal === "weather" && (
              <div className="form-box">
                <h2>Weather Constraints</h2>
                <input value={weatherData} onChange={e => setWeatherData(e.target.value)} placeholder="Weather constraints" />
              </div>
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