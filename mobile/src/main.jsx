import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

// Service worker — offline shell (PWA installable).
// Scope ya default ni /mobile/ — page inafunguliwa kwenye /mobile/ (backend inarekebisha /mobile → /mobile/).
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/mobile/sw.js").catch(() => {
      /* sw ni bonus — app inafanya kazi bila yake */
    });
  });
}

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
