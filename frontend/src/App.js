import { MapContainer, TileLayer, GeoJSON } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { useState } from "react";
import "./App.css";
import countriesData from "./data/countries.json";

export default function App() {
  const [selected, setSelected] = useState(null);
  const [mode, setMode] = useState("view");
  const [saved, setSaved] = useState(false);
  const [draft, setDraft] = useState({
    location: "",
    description: "",
    predicted: "",
    confidence: "",
    keywords: "",
  });

  const resetDraft = () => {
    setDraft({
      location: "",
      description: "",
      predicted: "",
      confidence: "",
      keywords: "",
    });
  };

  const onEachCountry = (feature, layer) => {
    layer.on({
      click: () => {
        setSelected(feature.properties.name);
        setMode("view");
      },
    });
  };

  const updateDraft = (field, value) => {
    setDraft({ ...draft, [field]: value });
    setSaved(false);
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
        {/* MENU */}
        <div className="menu-panel glass">
          <h1 className="menu-title">Disaster Response Planning System</h1>
          <div className="menu-buttons">
            <button>Active Incidents</button>
            <button>Resources</button>
            <button>Analytics</button>
            <button onClick={() => setMode("new")}>New Incident</button>
          </div>
        </div>

        {/* BOTTOM PANEL */}
        <div className="info-panel glass">
          {mode === "view" && (
            <>
              {selected ? (
                <>
                  <h2>{selected}</h2>
                  <p>Description will go here later</p>
                </>
              ) : (
                <p>Click a country</p>
              )}
            </>
          )}

          {mode === "new" && (
            <div className="form-box">
              <h2>New Incident</h2>

              <label>Location / Area</label>
              <input value={draft.location} onChange={e => updateDraft("location", e.target.value)} />

              <label>Description</label>
              <textarea value={draft.description} onChange={e => updateDraft("description", e.target.value)} />

              <label>Predicted Type</label>
              <input value={draft.predicted} onChange={e => updateDraft("predicted", e.target.value)} />

              <label>Confidence</label>
              <input value={draft.confidence} onChange={e => updateDraft("confidence", e.target.value)} />

              <label>Keywords Found</label>
              <input value={draft.keywords} onChange={e => updateDraft("keywords", e.target.value)} />

              <div className="form-buttons">
                <button onClick={() => {
                  resetDraft();
                  setSaved(false);
                  setMode("view");
                }}>
                  Submit
                </button>

                <button onClick={() => {
                  if (!saved) resetDraft();
                  setSaved(false);
                  setMode("view");
                }}>
                  Close
                </button>

                <button onClick={() => {
                  setSaved(true);
                  alert("Draft saved successfully!");
                }}>
                  Save Draft
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
