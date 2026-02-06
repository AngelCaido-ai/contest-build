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

type Channel = {
  id: number;
  tg_chat_id: number;
  username: string | null;
  title: string | null;
};

type Manager = {
  id: number;
  channel_id: number;
  user_id: number;
  tg_user_id: number;
  tg_username: string | null;
  permissions: Record<string, unknown> | null;
};

export default function App() {
  const [status, setStatus] = useState("");
  const [token, setToken] = useState(localStorage.getItem("token") ?? "");
  const [listings, setListings] = useState<Listing[]>([]);
  const [requests, setRequests] = useState<RequestItem[]>([]);
  const [deals, setDeals] = useState<Deal[]>([]);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [selectedChannelId, setSelectedChannelId] = useState<number | null>(null);
  const [managers, setManagers] = useState<Manager[]>([]);
  const [managerUsername, setManagerUsername] = useState("");
  const [managerStatus, setManagerStatus] = useState("");
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
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      const detail = typeof data?.detail === "string" ? data.detail : "API error";
      throw new Error(detail);
    }
    return data;
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

  const loadChannels = async () => {
    try {
      const items = await apiFetch("/channels");
      setChannels(items);
      if (items.length > 0 && selectedChannelId === null) {
        setSelectedChannelId(items[0].id);
      }
      setManagerStatus("");
    } catch (error) {
      setManagerStatus(error instanceof Error ? error.message : "API error");
    }
  };

  const loadManagers = async (channelId?: number) => {
    const id = channelId ?? selectedChannelId;
    if (!id) {
      setManagerStatus("Выберите канал");
      return;
    }
    try {
      const items = await apiFetch(`/channels/${id}/managers`);
      setManagers(items);
      setManagerStatus("");
    } catch (error) {
      setManagerStatus(error instanceof Error ? error.message : "API error");
    }
  };

  const addManager = async () => {
    const id = selectedChannelId;
    const username = managerUsername.trim();
    if (!id) {
      setManagerStatus("Выберите канал");
      return;
    }
    if (!username) {
      setManagerStatus("Введите @username");
      return;
    }
    try {
      await apiFetch(`/channels/${id}/managers`, {
        method: "POST",
        body: JSON.stringify({ tg_username: username }),
      });
      setManagerUsername("");
      setManagerStatus("Менеджер добавлен");
      await loadManagers(id);
    } catch (error) {
      setManagerStatus(error instanceof Error ? error.message : "API error");
    }
  };

  const removeManager = async (managerId: number) => {
    const id = selectedChannelId;
    if (!id) {
      setManagerStatus("Выберите канал");
      return;
    }
    try {
      await apiFetch(`/channels/${id}/managers/${managerId}`, { method: "DELETE" });
      setManagerStatus("Менеджер удален");
      await loadManagers(id);
    } catch (error) {
      setManagerStatus(error instanceof Error ? error.message : "API error");
    }
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
              <CardTitle>Managers</CardTitle>
              <CardDescription>Управление PR-менеджерами</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Button variant="secondary" size="sm" onClick={loadChannels}>
                  Load channels
                </Button>
                <Button variant="secondary" size="sm" onClick={() => loadManagers()}>
                  Load managers
                </Button>
                {managerStatus ? (
                  <div className="text-sm text-muted-foreground">{managerStatus}</div>
                ) : null}
              </div>
              <div className="flex flex-wrap gap-2">
                {channels.length === 0 ? (
                  <div className="text-sm text-muted-foreground">Каналы не загружены</div>
                ) : (
                  channels.map((channel) => {
                    const label = channel.title ?? channel.username ?? channel.tg_chat_id;
                    return (
                      <Button
                        key={channel.id}
                        variant={selectedChannelId === channel.id ? "default" : "outline"}
                        size="sm"
                        onClick={() => {
                          setSelectedChannelId(channel.id);
                          loadManagers(channel.id);
                        }}
                      >
                        #{channel.id} {label}
                      </Button>
                    );
                  })
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                <Input
                  placeholder="@username"
                  value={managerUsername}
                  onChange={(event) => setManagerUsername(event.target.value)}
                />
                <Button onClick={addManager}>Add manager</Button>
              </div>
              <div className="space-y-2">
                {managers.length === 0 ? (
                  <div className="text-sm text-muted-foreground">Менеджеры не загружены</div>
                ) : (
                  managers.map((manager) => (
                    <div
                      key={manager.id}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-md border bg-background px-3 py-2 text-sm"
                    >
                      <div>
                        #{manager.id} @{manager.tg_username ?? "-"} tg_user_id={manager.tg_user_id}
                      </div>
                      <Button variant="outline" size="sm" onClick={() => removeManager(manager.id)}>
                        Remove
                      </Button>
                    </div>
                  ))
                )}
              </div>
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
