export type Listing = {
  id: number;
  channel_id: number;
  price_ton: number | null;
  price_usd: number | null;
  format: string;
  categories: string[] | null;
  constraints: Record<string, unknown> | null;
  active: boolean;
  created_at: string;
  channel?: Channel;
};

export type ChannelBrief = {
  id: number;
  username: string | null;
  title: string | null;
  stats: ChannelStats | null;
};

export type ListingDetail = Omit<Listing, "channel"> & {
  channel?: ChannelBrief | null;
};

export type RequestItem = {
  id: number;
  advertiser_id: number;
  budget: number | null;
  niche: string | null;
  languages: string[] | null;
  min_subs: number | null;
  min_views: number | null;
  dates: Record<string, unknown> | null;
  brief: string | null;
  created_at: string;
};

export type DealStatus =
  | "NEGOTIATING"
  | "TERMS_LOCKED"
  | "AWAITING_PAYMENT"
  | "FUNDED"
  | "CREATIVE_DRAFT"
  | "CREATIVE_REVIEW"
  | "APPROVED"
  | "SCHEDULED"
  | "POSTED"
  | "VERIFYING"
  | "RELEASED"
  | "REFUNDED"
  | "CANCELED";

export type Deal = {
  id: number;
  listing_id: number | null;
  request_id: number | null;
  advertiser_id: number;
  channel_id: number;
  price: number | null;
  format: string | null;
  brief: string | null;
  publish_at: string | null;
  verification_window: number | null;
  status: DealStatus;
  posted_message_id: number | null;
  posted_at: string | null;
  verification_started_at: string | null;
  tampered: boolean;
  deleted: boolean;
  created_at: string;
  updated_at: string;
  channel?: Channel;
};

export type DealChannelBrief = {
  id: number;
  username: string | null;
  title: string | null;
  subscribers: number | null;
  views_per_post: number | null;
};

export type DealAdvertiserBrief = {
  id: number;
  tg_username: string | null;
};

export type DealDetail = Deal & {
  channel_info?: DealChannelBrief | null;
  advertiser_info?: DealAdvertiserBrief | null;
  events?: DealEvent[];
};

export type Channel = {
  id: number;
  tg_chat_id: number;
  username: string | null;
  title: string | null;
  owner_user_id: number;
  bot_admin_status: boolean;
  created_at: string;
  stats?: ChannelStats;
};

export type ChannelStats = {
  id: number;
  channel_id: number;
  subscribers: number | null;
  views_per_post: number | null;
  languages_json: Record<string, unknown> | null;
  premium_json: Record<string, unknown> | null;
  updated_at: string | null;
  source: string | null;
};

export type Manager = {
  id: number;
  channel_id: number;
  user_id: number;
  tg_user_id: number;
  tg_username: string | null;
  permissions: Record<string, unknown> | null;
};

export type TgAdmin = {
  tg_user_id: number;
  tg_username: string | null;
  first_name: string;
  status: string;
};

export type DealEvent = {
  id: number;
  deal_id: number;
  type: string;
  payload: Record<string, unknown> | null;
  created_at: string;
};

export type MediaFileId = {
  type: "photo" | "video" | "animation" | "document";
  file_id: string;
};

export type EscrowPayment = {
  id: number;
  deal_id: number;
  deposit_address: string;
  deposit_comment: string | null;
  deposit_key: string | null;
  expected_amount: number | null;
  tx_hash: string | null;
  confirmed_at: string | null;
  release_tx_hash: string | null;
  refund_tx_hash: string | null;
  payout_address: string | null;
  refund_address: string | null;
  released_at: string | null;
  refunded_at: string | null;
  created_at: string;
};

export type User = {
  id: number;
  tg_user_id: number;
  tg_username: string | null;
  roles: string[];
  linked_wallet: string | null;
};
