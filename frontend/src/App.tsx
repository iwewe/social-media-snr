import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";

import { useAuth } from "./auth/context";
import { InvestigationPage } from "./pages/InvestigationPage";
import { InvestigationsPage } from "./pages/InvestigationsPage";
import { LoginPage } from "./pages/LoginPage";
import { RunPage } from "./pages/RunPage";

function Layout() {
  const { user, logout } = useAuth();
  const location = useLocation();

  if (user === undefined) return <p className="muted">Memeriksa sesi...</p>;
  if (user === null) return <Navigate to="/login" replace state={{ from: location.pathname }} />;

  return (
    <div className="app">
      <header className="topbar">
        <strong>SNR</strong>
        <span>
          {user.username}{" "}
          <button type="button" onClick={() => void logout()}>
            Keluar
          </button>
        </span>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<Layout />}>
        <Route path="/" element={<InvestigationsPage />} />
        <Route path="/investigations/:id" element={<InvestigationPage />} />
        <Route path="/inspections/:id" element={<RunPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
