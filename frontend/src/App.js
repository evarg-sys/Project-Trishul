import { MapContainer, TileLayer, GeoJSON } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { useState } from "react";
import "./App.css";
import countriesData from "./data/countries.json";

export default function App() {
  const [selected, setSelected] = useState(null);
  const [view, setView] = useState("country"); // country | new | incidents | analytics | resources
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

  const resetDraft = () => {
    setDraft({
      location: "",
      description: "",
      predicted: "",
      confidence: "",
      keywords: "",
    });
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
              <div className="incident-box" onClick={() => setModal("severity")}>Severity Score</div>
              <div className="incident-box" onClick={() => setModal("population")}>Population / Exposure</div>
              <div className="incident-box" onClick={() => setModal("routing")}>Routing & Travel Time</div>
              <div className="incident-box" onClick={() => setModal("feasibility")}>Feasibility Score</div>
              <div className="incident-box" onClick={() => setModal("ambulances")}>Ambulances Ready?</div>
              <div className="incident-box" onClick={() => setModal("weather")}>Weather Constraints?</div>
            </>
          )}

          {view === "new" && (
            <div className="form-box">
              <h2>New Incident</h2>
              <label>Location / Area</label>
              <input value={draft.location} onChange={e=>updateDraft("location", e.target.value)} />
              <label>Description</label>
              <textarea value={draft.description} onChange={e=>updateDraft("description", e.target.value)} />
              <label>Predicted Type</label>
              <input value={draft.predicted} onChange={e=>updateDraft("predicted", e.target.value)} />
              <label>Confidence</label>
              <input value={draft.confidence} onChange={e=>updateDraft("confidence", e.target.value)} />
              <label>Keywords Found</label>
              <input value={draft.keywords} onChange={e=>updateDraft("keywords", e.target.value)} />

              <div className="form-buttons">
                <button onClick={() => { resetDraft(); setSaved(false); setView("country"); }}>Submit</button>
                <button onClick={() => { if(!saved) resetDraft(); setSaved(false); setView("country"); }}>Close</button>
                <button onClick={() => { setSaved(true); alert("Draft saved successfully!"); }}>Save Draft</button>
              </div>
            </div>
          )}

          {view === "analytics" && (
            <div className="analytics-box">
              <h2>Analytics</h2>
              <div className="row"><label>Average Response Time:</label><input /></div>
              <div className="row"><label>AI Accuracy:</label><input /></div>
              <div className="row"><label>Active Incidents:</label><input /></div>
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
            <div className="resources-scene">
              <h2>Resources</h2>
              <div className="resource-top-buttons">
                <button>Fire Trucks</button>
                <button>Ambulances</button>
                <button>Police Units</button>
                <button>Others</button>
              </div>

              <div className="resources-grid">
                <div className="resource-panel glass">
                  <h3>All Resources</h3>
                  <div className="row"><label>Fire Trucks Availability:</label><input /></div>
                  <div className="row"><label>Ambulance Availability:</label><input /></div>
                  <div className="row"><label>Police Units Availability:</label><input /></div>
                  <div className="row"><label>Other Availability:</label><input /></div>
                  <div className="row"><label>Total Availability:</label><input /></div>
                </div>

                <div className="resource-panel glass">
                  <h3>[Resource Chosen]</h3>
                  <div className="row"><label>Name:</label><input /></div>
                  <div className="row"><label>Status:</label><input /></div>
                  <div className="row"><label>Closest Location Distance:</label><input /></div>
                  <div className="row"><label>Last Active:</label><input /></div>
                  <div className="row"><label>Estimated Response Time:</label><input /></div>
                  <div className="resource-actions">
                    <button>Assign</button>
                    <button>Reserve</button>
                    <button>Disable</button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* MODALS (unchanged) */}
      {modal && (
        <div className="modal-overlay">
          <div className="modal glass">
            {modal === "incidentList" && <h2>Full Incident List (placeholder)</h2>}

            {modal === "severity" && (
              <div className="severity-box">
                <h2>Severity Scaling</h2>
                <label>Input:</label>
                <input value={severityInput} onChange={e=>setSeverityInput(e.target.value)} />
                <label>Severity Score:</label>
                <input value={severityScore} onChange={e=>setSeverityScore(e.target.value)} />
                <label>Notes (Keywords Found):</label>
                <textarea value={severityNotes} onChange={e=>setSeverityNotes(e.target.value)} />
              </div>
            )}

            {modal === "population" && (
              <div className="population-box">
                <h2>Population / Exposure</h2>
                <div className="row"><label>Area Size:</label><input value={populationData.area} onChange={e=>setPopulationData({...populationData, area: e.target.value})}/></div>
                <div className="row"><label>Buildings in Area:</label><input value={populationData.buildings} onChange={e=>setPopulationData({...populationData, buildings: e.target.value})}/></div>
                <div className="row"><label>Dominant Building:</label><input value={populationData.type} onChange={e=>setPopulationData({...populationData, type: e.target.value})}/></div>
                <div className="row"><label>Estimated People:</label><input value={populationData.people} onChange={e=>setPopulationData({...populationData, people: e.target.value})}/></div>
              </div>
            )}

            {modal === "routing" && (
              <div className="routing-box">
                <h2>Routing and Travel Time</h2>
                <div className="row"><label>Nearest Station:</label><input value={routingData.station} onChange={e=>setRoutingData({...routingData, station:e.target.value})}/></div>
                <div className="row"><label>ETA (current):</label><input value={routingData.eta} onChange={e=>setRoutingData({...routingData, eta:e.target.value})}/></div>
                <div className="row"><label>Traffic:</label><input value={routingData.traffic} onChange={e=>setRoutingData({...routingData, traffic:e.target.value})}/></div>
                <div className="row"><label>Closures/Blocks:</label><input value={routingData.blocks} onChange={e=>setRoutingData({...routingData, blocks:e.target.value})}/></div>
              </div>
            )}

            {modal === "feasibility" && <input value={feasibilityData} onChange={e=>setFeasibilityData(e.target.value)} placeholder="Feasibility score" />}
            {modal === "ambulances" && <input value={ambulanceData} onChange={e=>setAmbulanceData(e.target.value)} placeholder="Ambulances ready?" />}
            {modal === "weather" && <input value={weatherData} onChange={e=>setWeatherData(e.target.value)} placeholder="Weather constraints" />}

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
