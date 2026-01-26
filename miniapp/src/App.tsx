import { useEffect, useState } from "react";

import { Button } from "./components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./components/ui/card";
import { Input } from "./components/ui/input";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
const BOT_URL = import.meta.env.VITE_BOT_URL ?? "https://t.me/";

type Listing = {
  id: number;
  channel_id: number;
  price_usd: number | null;
};

type RequestItem = {
  id: number;
  budget: number | null;
  brief: string | null;
};

type Deal = {
  id: number;
  status: string;
};

export default function App() {
  const [status, setStatus] = useState("");
  const [token, setToken] = useState(localStorage.getItem("token") ?? "");
  const [listings, setListings] = useState<Listing[]>([]);
  const [requests, setRequests] = useState<RequestItem[]>([]);
  const [deals, setDeals] = useState<Deal[]>([]);
  const [reqBrief, setReqBrief] = useState("");
  const [reqBudget, setReqBudget] = useState("");
  const [listingChannelId, setListingChannelId] = useState("");
  const [listingPrice, setListingPrice] = useState("");

  const authenticate = async () => {
    const tg = window.Telegram?.WebApp;
    const initData = tg?.initData ?? "";
    if (!initData) {
      setStatus("initData missing");
      return;
    }
    const res = await fetch(`${API_BASE}/auth/miniapp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ init_data: initData }),
    });
    if (!res.ok) {
      setStatus("Auth failed");
      return;
    }
    const data = await res.json();
    localStorage.setItem("token", data.token);
    setToken(data.token);
    setStatus("Authenticated");
  };

  const apiFetch = async (path: string, options: RequestInit = {}) => {
    const headers = { ...(options.headers ?? {}) } as Record<string, string>;
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    headers["Content-Type"] = "application/json";
    const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
    if (!res.ok) {
      throw new Error("API error");
    }
    return res.json();
  };

  const loadListings = async () => {
    const items = await apiFetch("/listings");
    setListings(items);
  };

  const loadRequests = async () => {
    const items = await apiFetch("/requests");
    setRequests(items);
  };

  const loadDeals = async () => {
    const items = await apiFetch("/deals");
    setDeals(items);
  };

  const createRequest = async () => {
    const budget = reqBudget ? parseFloat(reqBudget) : null;
    const brief = reqBrief || null;
    await apiFetch("/requests", {
      method: "POST",
      body: JSON.stringify({ budget, brief }),
    });
    setStatus("Request created");
  };

  const createListing = async () => {
    const channel_id = listingChannelId ? parseInt(listingChannelId, 10) : null;
    const price_usd = listingPrice ? parseFloat(listingPrice) : null;
    await apiFetch("/listings", {
      method: "POST",
      body: JSON.stringify({ channel_id, price_usd, format: "post" }),
    });
    setStatus("Listing created");
  };

  const openBot = () => {
    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.openTelegramLink(BOT_URL);
      return;
    }
    setStatus("Telegram WebApp not available");
  };

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (tg?.ready) {
      tg.ready();
    }
    authenticate();
  }, []);

  const statusLabel = status || (token ? "Ready" : "Not authenticated");

  return (
    <div className="min-h-screen bg-muted/40">
      <div className="mx-auto max-w-5xl px-4 py-8">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">Marketplace</h1>
            <p className="text-sm text-muted-foreground">
              Listings, requests and deals in one mini app
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center rounded-full bg-secondary px-3 py-1 text-xs text-secondary-foreground">
              {statusLabel}
            </span>
            <Button variant="secondary" size="sm" onClick={authenticate}>
              Re-auth
            </Button>
          </div>
        </div>

        <div className="mt-6 grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Listings</CardTitle>
              <CardDescription>Каталог каналов и цен</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button variant="secondary" size="sm" onClick={loadListings}>
                Load listings
              </Button>
              <div className="space-y-2">
                {listings.length === 0 ? (
                  <div className="text-sm text-muted-foreground">No listings loaded</div>
                ) : (
                  listings.map((item) => (
                    <div key={item.id} className="rounded-md border bg-background px-3 py-2 text-sm">
                      #{item.id} channel={item.channel_id} price={item.price_usd ?? "-"}
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Requests</CardTitle>
              <CardDescription>Запросы рекламодателей</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button variant="secondary" size="sm" onClick={loadRequests}>
                Load requests
              </Button>
              <div className="space-y-2">
                {requests.length === 0 ? (
                  <div className="text-sm text-muted-foreground">No requests loaded</div>
                ) : (
                  requests.map((item) => (
                    <div key={item.id} className="rounded-md border bg-background px-3 py-2 text-sm">
                      #{item.id} budget={item.budget ?? "-"} brief={item.brief ?? ""}
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Create Request</CardTitle>
              <CardDescription>Бриф и бюджет на размещение</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Input
                placeholder="Brief"
                value={reqBrief}
                onChange={(event) => setReqBrief(event.target.value)}
              />
              <Input
                type="number"
                placeholder="Budget"
                value={reqBudget}
                onChange={(event) => setReqBudget(event.target.value)}
              />
              <Button onClick={createRequest}>Create request</Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Create Listing</CardTitle>
              <CardDescription>Канал и цена размещения</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Input
                type="number"
                placeholder="Channel ID"
                value={listingChannelId}
                onChange={(event) => setListingChannelId(event.target.value)}
              />
              <Input
                type="number"
                placeholder="Price USD"
                value={listingPrice}
                onChange={(event) => setListingPrice(event.target.value)}
              />
              <Button onClick={createListing}>Create listing</Button>
            </CardContent>
          </Card>

          <Card className="md:col-span-2">
            <CardHeader>
              <CardTitle>Deals</CardTitle>
              <CardDescription>Статусы текущих сделок</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button variant="secondary" size="sm" onClick={loadDeals}>
                Load deals
              </Button>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {deals.length === 0 ? (
                  <div className="text-sm text-muted-foreground">No deals loaded</div>
                ) : (
                  deals.map((item) => (
                    <div key={item.id} className="rounded-md border bg-background px-3 py-2 text-sm">
                      #{item.id} status={item.status}
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

          <Card className="md:col-span-2">
            <CardHeader>
              <CardTitle>Open Bot</CardTitle>
              <CardDescription>Переход в текстового бота по сделке</CardDescription>
            </CardHeader>
            <CardContent>
              <Button variant="outline" onClick={openBot}>
                Go to bot
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
