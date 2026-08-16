import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import { SettingsPage } from "./pages/SettingsPage";
import { ImportPage } from "./pages/ImportPage";
import { PlayersPage } from "./pages/PlayersPage";
import { PlayerDetailPage } from "./pages/PlayerDetailPage";

export default function App() {
  return (
    <BrowserRouter>
      <nav style={{ padding: 8, borderBottom: "1px solid #ccc" }}>
        <Link to="/" style={{ marginRight: 12 }}>Settings</Link>
        <Link to="/import" style={{ marginRight: 12 }}>Import</Link>
        <Link to="/players">Players</Link>
      </nav>
      <main style={{ padding: 16 }}>
        <Routes>
          <Route path="/" element={<SettingsPage />} />
          <Route path="/import" element={<ImportPage />} />
          <Route path="/players" element={<PlayersPage />} />
          <Route path="/players/:id" element={<PlayerDetailPage />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
