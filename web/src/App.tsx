import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { PresetProvider, usePreset } from "./context/PresetContext";
import { PresetSelector } from "./components/PresetSelector";
import { SettingsPage } from "./pages/SettingsPage";
import { ImportPage } from "./pages/ImportPage";
import { PlayersPage } from "./pages/PlayersPage";
import { PlayerDetailPage } from "./pages/PlayerDetailPage";

function Shell() {
  const { preset, setPreset } = usePreset();
  return (
    <AppShell
      preset={preset ? <PresetSelector value={preset} onChange={setPreset} /> : null}
    >
      <Routes>
        <Route path="/" element={<SettingsPage />} />
        <Route path="/import" element={<ImportPage />} />
        <Route path="/players" element={<PlayersPage />} />
        <Route path="/players/:id" element={<PlayerDetailPage />} />
      </Routes>
    </AppShell>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <PresetProvider>
        <Shell />
      </PresetProvider>
    </BrowserRouter>
  );
}
