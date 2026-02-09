import { HashRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./contexts/AuthContext";
import { Layout } from "./components/Layout";
import { ListingsPage } from "./pages/ListingsPage";
import { RequestsPage } from "./pages/RequestsPage";
import { ChannelsPage } from "./pages/ChannelsPage";
import { DealsPage } from "./pages/DealsPage";
import { DealDetailPage } from "./pages/DealDetailPage";
import { PaymentPage } from "./pages/PaymentPage";

export default function App() {
  return (
    <HashRouter>
      <AuthProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Navigate to="/listings" replace />} />
            <Route path="/listings" element={<ListingsPage />} />
            <Route path="/requests" element={<RequestsPage />} />
            <Route path="/channels" element={<ChannelsPage />} />
            <Route path="/deals" element={<DealsPage />} />
            <Route path="/deals/:id" element={<DealDetailPage />} />
            <Route path="/deals/:id/pay" element={<PaymentPage />} />
          </Route>
        </Routes>
      </AuthProvider>
    </HashRouter>
  );
}
