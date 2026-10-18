import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles/tokens.css";
import "./styles/app.css";

createRoot(document.getElementById("racine")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
