import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { ActivityPage } from "./pages/Activity";
import { BodyPage } from "./pages/Body";
import { DataPage } from "./pages/Data";
import { OverviewPage } from "./pages/Overview";
import { SleepPage } from "./pages/Sleep";
import { WorkoutsPage } from "./pages/Workouts";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/activity" element={<ActivityPage />} />
          <Route path="/workouts" element={<WorkoutsPage />} />
          <Route path="/sleep" element={<SleepPage />} />
          <Route path="/body" element={<BodyPage />} />
          <Route path="/data" element={<DataPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
