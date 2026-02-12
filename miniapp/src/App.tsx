import { HashRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./contexts/AuthContext";
import { Layout } from "./components/Layout";
import { ListingsPage } from "./pages/ListingsPage";
import { ListingDetailPage } from "./pages/ListingDetailPage";
import { RequestsPage } from "./pages/RequestsPage";
import { RequestDetailPage } from "./pages/RequestDetailPage";
import { ChannelsPage } from "./pages/ChannelsPage";
import { DealsPage } from "./pages/DealsPage";
import { DealDetailPage } from "./pages/DealDetailPage";
import { PaymentPage } from "./pages/PaymentPage";
import { AddChannelPage } from "./pages/AddChannelPage";
import { WalletPage } from "./pages/WalletPage";
import { CreateListingPage } from "./pages/CreateListingPage";
import { CreateRequestPage } from "./pages/CreateRequestPage";

export default function App() {
  return (
    <HashRouter>
      <AuthProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Navigate to="/listings" replace />} />
            <Route path="/listings" element={<ListingsPage />} />
            <Route path="/listings/new" element={<CreateListingPage />} />
            <Route path="/listings/:id" element={<ListingDetailPage />} />
            <Route path="/requests" element={<RequestsPage />} />
            <Route path="/requests/new" element={<CreateRequestPage />} />
            <Route path="/requests/:id" element={<RequestDetailPage />} />
            <Route path="/channels" element={<ChannelsPage />} />
            <Route path="/channels/new" element={<AddChannelPage />} />
            <Route path="/wallet" element={<WalletPage />} />
            <Route path="/deals" element={<DealsPage />} />
            <Route path="/deals/:id" element={<DealDetailPage />} />
            <Route path="/deals/:id/pay" element={<PaymentPage />} />
            <Route path="*" element={<Navigate to="/listings" replace />} />
          </Route>
        </Routes>
      </AuthProvider>
    </HashRouter>
  );
}
