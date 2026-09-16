const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

export interface IndexData {
  name: string;
  value: number;
  change: number;
  change_pct: number;
}

export interface StockQuote {
  symbol: string;
  price: number;
  prev_close: number;
  change: number;
  change_pct: number;
  open: number;
  high: number;
  low: number;
  volume: number;
  year_high: number;
  year_low: number;
  market_cap: number;
  vwap?: number;
  delivery_pct?: number;
  lower_circuit?: number;
  upper_circuit?: number;
}

export interface HistoryPoint {
  time: number;
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Fundamentals {
  name?: string;
  pe_ratio?: number;
  forward_pe?: number;
  pb_ratio?: number;
  roe?: number;
  roa?: number;
  debt_equity?: number;
  current_ratio?: number;
  gross_margin?: number;
  operating_margin?: number;
  net_margin?: number;
  revenue_growth?: number;
  earnings_growth?: number;
  market_cap?: number;
  book_value?: number;
  dividend_yield?: number;
  eps?: number;
  forward_eps?: number;
  sector?: string;
  industry?: string;
  employees?: number;
  description?: string;
}

export interface TechnicalIndicators {
  current_price: number;
  sma_20: number;
  sma_50?: number;
  sma_200?: number;
  ema_20: number;
  ema_50?: number;
  rsi_14: number;
  rsi_signal: string;
  macd: number;
  macd_signal: number;
  macd_histogram: number;
  macd_crossover: string;
  bb_upper: number;
  bb_mid: number;
  bb_lower: number;
  atr: number;
  volume_ratio: number;
  resistance_1: number;
  support_1: number;
  trend: string;
  signals: string[];
}

export interface AgentResult {
  agent: string;
  confidence: number;
  signal: string;
  summary: string;
  findings: string[];
  data: Record<string, unknown>;
}

export interface AnalysisResult {
  symbol: string;
  timestamp: string;
  live_data: StockQuote;
  agents: {
    fundamentals: AgentResult;
    technical: AgentResult;
    macro: AgentResult;
    risk: AgentResult;
  };
  debate: {
    bull_confidence: number;
    bear_confidence: number;
    consensus: string;
    bull_arguments: string[];
    bear_arguments: string[];
    bull_target: number;
    bear_target: number;
    expected_value: number;
  };
  final_decision: {
    decision: string;
    entry_price: number;
    stop_loss: number;
    target_price: number;
    position_size_pct: number;
    risk_reward: number;
    rationale: string;
  };
}

export interface OptionData {
  strike: number;
  expiry: string;
  ce_oi: number;
  ce_change_oi: number;
  ce_iv: number;
  ce_ltp: number;
  ce_volume: number;
  pe_oi: number;
  pe_change_oi: number;
  pe_iv: number;
  pe_ltp: number;
  pe_volume: number;
  pcr: number;
}

export interface NewsArticle {
  title: string;
  url: string;
  source: string;
  published: string;
  age_hours: number;
  age_days: number;
  summary: string;
  sentiment: "positive" | "negative" | "neutral";
  tags: string[];
}

export interface AnalystRating {
  date: string;
  firm: string;
  action: string;
  from_grade: string;
  to_grade: string;
}

export interface AnalystData {
  strong_buy: number;
  buy: number;
  hold: number;
  sell: number;
  strong_sell: number;
  total_analysts: number;
  bull_pct: number;
  recommendation: string;
  score?: number;
  recent_ratings: AnalystRating[];
}

export interface TrendBreakdown {
  technical: number;
  momentum: number;
  analyst: number;
  sentiment: number;
}

export interface TrendScore {
  overall: number;
  breakdown: TrendBreakdown;
  label: string;
  color: string;
  signals: string[];
  news_count: number;
  positive_news: number;
  negative_news: number;
}

export interface UniverseEntry {
  symbol: string;
  company_name: string;
  category: "nifty50" | "nifty100" | "psu";
}

export interface MacroTicker {
  label: string;
  symbol: string;
  price: number;
  change_pct: number;
}

export interface MCBands {
  p5: number[]; p25: number[]; p50: number[]; p75: number[]; p95: number[];
}

export interface MCResult {
  symbol: string;
  current_price: number;
  days: number;
  simulations: number;
  daily_volatility_pct: number;
  annual_volatility_pct: number;
  daily_drift_pct: number;
  bands: MCBands;
  var_95_pct: number;
  var_99_pct: number;
  cvar_95_pct: number;
  expected_price: number;
  expected_return_pct: number;
  prob_profit_pct: number;
  prob_up5_pct: number;
  prob_down5_pct: number;
  prob_down10_pct: number;
  price_range_95: { low: number; high: number };
}

export interface PairData {
  sym1: string; sym2: string;
  hedge_ratio: number; alpha: number;
  current_zscore: number;
  half_life_days: number | null;
  correlation: number;
  signal: string;
  signal_color: string;
  action: string;
  zscore_series: number[];
  lookback: number;
  dates?: string[];
}

export interface CorrelationResult {
  symbols: string[];
  matrix: Record<string, Record<string, number>>;
  top_correlated: { sym1: string; sym2: string; corr: number }[];
  least_correlated: { sym1: string; sym2: string; corr: number }[];
  negative_corr: { sym1: string; sym2: string; corr: number }[];
}

export interface BreadthData {
  total: number; advances: number; declines: number; unchanged: number;
  adr: number;
  pct_above_50dma: number;
  pct_above_200dma: number;
  median_rsi: number;
  pct_overbought: number;
  pct_oversold: number;
  near_52w_high: number;
  near_52w_low: number;
  breadth_signal: string;
  breadth_color: string;
}

export interface SectorData {
  sector: string;
  avg_change_pct: number;
  stock_count: number;
  advances: number;
  declines: number;
  stocks: { symbol: string; price: number; change_pct: number }[];
}

export interface SectorSpotlight {
  sector: string;
  shine_score: number;
  mom_1d: number;
  mom_5d: number;
  breadth_pct: number;
  vol_surge: number;
  advances: number;
  total: number;
  label: string;
  color: string;
}

async function get<T>(path: string, retries = 2, timeoutMs = 12000): Promise<T> {
  let lastErr: Error = new Error("fetch failed");
  for (let i = 0; i <= retries; i++) {
    const controller = new AbortController();
    const tid = setTimeout(() => controller.abort(new DOMException("Timeout", "AbortError")), timeoutMs);
    try {
      const res = await fetch(`${BASE}${path}`, {
        cache: "no-store",
        signal: controller.signal,
      });
      clearTimeout(tid);
      if (!res.ok) throw new Error(`API ${res.status} ${path}`);
      return res.json() as Promise<T>;
    } catch (e) {
      clearTimeout(tid);
      lastErr = e as Error;
      // Don't retry on abort (timeout) — the request took too long, retry won't help immediately
      if ((e as Error).name === "AbortError") break;
      if (i < retries) await new Promise(r => setTimeout(r, 600 * (i + 1)));
    }
  }
  throw lastErr;
}

async function nse<T>(type: string, params: Record<string, string> = {}): Promise<T> {
  const qs = new URLSearchParams({ type, ...params }).toString();
  const res = await fetch(`/api/nse?${qs}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`NSE ${res.status} ${type}`);
  return res.json() as Promise<T>;
}

export const api = {
  indices: () => get<IndexData[]>("/api/indices"),
  marketOverview: () => get<{ indices: IndexData[]; watchlist: StockQuote[] }>("/api/market/overview"),
  fiiDii: () => get<unknown>("/api/market/fii-dii"),
  marketStatus: () => get<{ is_open: boolean; message: string }>("/api/market/status"),
  quote: (symbol: string) => get<StockQuote>(`/api/quote/${symbol}`),
  history: (symbol: string, period = "1y", interval = "1d") =>
    get<{ symbol: string; data: HistoryPoint[] }>(`/api/history/${symbol}?period=${period}&interval=${interval}`),
  technicals: (symbol: string) =>
    get<{ symbol: string; indicators: TechnicalIndicators }>(`/api/technicals/${symbol}`),
  fundamentals: (symbol: string) =>
    get<{ symbol: string; fundamentals: Fundamentals }>(`/api/fundamentals/${symbol}`),
  options: (symbol: string) =>
    get<{ symbol: string; underlying_value: number; expiry_dates: string[]; data: OptionData[] }>(`/api/options/${symbol}`),
  analysis: (symbol: string) => get<AnalysisResult>(`/api/analysis/${symbol}`),
  search: (q: string) => get<StockQuote[]>(`/api/search?q=${encodeURIComponent(q)}`),
  gainers: () => get<StockQuote[]>("/api/screener/gainers"),
  losers: () => get<StockQuote[]>("/api/screener/losers"),
  nifty50: () => get<StockQuote[]>("/api/screener/nifty50"),
  psu: () => get<StockQuote[]>("/api/screener/psu"),
  universe: () => get<UniverseEntry[]>("/api/screener/universe"),
  news: (symbol: string) =>
    get<{ symbol: string; company: string; total: number; articles: NewsArticle[] }>(`/api/news/${symbol}`),
  marketNews: () =>
    get<{ total: number; articles: NewsArticle[] }>("/api/news/market/feed"),
  analysts: (symbol: string) =>
    get<{ symbol: string; data: AnalystData }>(`/api/analysts/${symbol}`),
  trends: (symbol: string) =>
    get<{ symbol: string; company: string; live: StockQuote; trend: TrendScore; analysts: AnalystData; news_preview: NewsArticle[] }>(`/api/trends/${symbol}`),
  portfolio: () => get<unknown>("/api/portfolio"),
  // ── New quantitative endpoints
  macro: () => get<{ data: MacroTicker[] }>("/api/macro"),
  montecarlo: (symbol: string, days = 30) =>
    get<MCResult>(`/api/montecarlo/${symbol}?days=${days}`),
  correlation: (symbols: string) =>
    get<CorrelationResult>(`/api/correlation?symbols=${encodeURIComponent(symbols)}`),
  pairs: () => get<{ pairs: PairData[] }>("/api/pairs"),
  pairDetail: (sym1: string, sym2: string) =>
    get<PairData>(`/api/pairs/${sym1}/${sym2}`),
  screenerMomentum: () =>
    get<{ type: string; results: Record<string, unknown>[] }>("/api/screener/momentum", 1, 90000),
  screenerMeanRev: () =>
    get<{ type: string; results: Record<string, unknown>[] }>("/api/screener/meanrev", 1, 90000),
  screenerBreakout: () =>
    get<{ type: string; results: Record<string, unknown>[] }>("/api/screener/breakout", 1, 90000),
  screenerVolume: () =>
    get<{ type: string; results: Record<string, unknown>[] }>("/api/screener/volume", 1, 90000),
  optionsAnalytics: (symbol: string) => get<unknown>(`/api/options/analytics/${symbol}`),
  breadth: () => get<BreadthData>("/api/breadth"),
  sectors: () => get<{ sectors: SectorData[] }>("/api/sectors"),
  // ── NSE direct (via Next.js API route proxy — avoids CORS)
  nseTradeInfo: (symbol: string) => nse<unknown>("trade-info", { symbol }),
  nseCorporateInfo: (symbol: string) => nse<unknown>("corporate-info", { symbol }),
  nsePreOpen: () => nse<unknown>("pre-open"),
  nseDailyReports: () => nse<unknown>("daily-reports"),
  nseCirculars: () => nse<unknown>("circulars"),
  nseMarketTurnover: () => nse<unknown>("market-turnover"),
  nseTechnicals: (symbol: string) => nse<unknown>("technical", { symbol }),
  // ── Deep analytics endpoints
  earnings: (symbol: string) => get<unknown>(`/api/earnings/${symbol}`),
  compare: (sym1: string, sym2: string, period = "1Y") =>
    get<unknown>(`/api/compare/${sym1}/${sym2}?period=${period}`),
  volumeScan: () => get<{ data: unknown[]; computed_at: string }>("/api/volume-scan"),
  sharpe: (symbol: string) => get<unknown>(`/api/sharpe/${symbol}`),
  events: () => get<{ events: unknown[] }>("/api/events"),
  eventAnalysis: (eventId: string) => get<unknown>(`/api/event-analysis/${eventId}`),
  geoNews: () => get<{ articles: unknown[]; count: number }>("/api/geo-news"),
  dividendAnalysis: (symbol: string) => get<unknown>(`/api/dividend-analysis/${symbol}`),
  // ── Global Macro
  globalMacro: () => get<unknown>("/api/global-macro"),
  yieldCurve: () => get<unknown>("/api/yield-curve"),
  crossCorrelation: (period = "1y") => get<unknown>(`/api/cross-correlation?period=${period}`),
  macroRegime: () => get<unknown>("/api/macro-regime"),
  crossAssetMomentum: () => get<unknown>("/api/cross-asset-momentum"),
  indiaMacroSensitivity: () => get<unknown>("/api/india-macro-sensitivity"),
  shipping: () => get<unknown>("/api/shipping"),
  geopoliticalRisk: () => get<unknown>("/api/geopolitical-risk"),
  // ── Institutional
  fiiDiiDaily: () => get<unknown>("/api/fii-dii/daily"),
  bulkDeals: () => get<unknown>("/api/bulk-deals"),
  blockDeals: () => get<unknown>("/api/block-deals"),
  institutionalHoldings: (symbol: string) => get<unknown>(`/api/institutional-holdings/${symbol}`),
  mfIntelligence: (symbol: string) => get<unknown>(`/api/mf-intelligence/${symbol}`),
  fiiSectorFlow: () => get<unknown>("/api/fii-sector-flow"),
  oiBuildup: (symbol: string) => get<unknown>(`/api/oi-buildup/${symbol}`),
  corporateActions: (symbol: string) => get<unknown>(`/api/corporate-actions/${symbol}`),
  // ── Quant Models
  marketRegime: (symbol: string, period = "2y") => get<unknown>(`/api/market-regime/${symbol}?period=${period}`),
  volatilityRegime: (symbol: string) => get<unknown>(`/api/volatility-regime/${symbol}`),
  factorModel: (symbol: string) => get<unknown>(`/api/factor-model/${symbol}`),
  arbitrageScan: () => get<unknown>("/api/arbitrage-scan"),
  kellyCriterion: (symbol: string) => get<unknown>(`/api/kelly/${symbol}`),
  meanReversion: (symbol: string) => get<unknown>(`/api/mean-reversion/${symbol}`),
  adaptiveStrategy: (symbol: string) => get<unknown>(`/api/adaptive-strategy/${symbol}`),
  repeatingPatterns: () => get<unknown>("/api/repeating-patterns"),
  // ── Recommendations
  recommend: (symbol: string) => get<unknown>(`/api/recommend/${symbol}`),
  recommendations: (limit = 50) => get<unknown>(`/api/recommendations?limit=${limit}`),
  sectorRotation: () => get<unknown>("/api/sector-rotation"),
  // ── New analysis endpoints
  patterns: (symbol: string, period = "3mo") =>
    get<{ symbol: string; trend: string; patterns: unknown[]; support: number; resistance: number; ma5: number; ma20: number; mean_reversion: unknown; breakout: unknown }>(`/api/patterns/${symbol}?period=${period}`),
  greeks: (symbol: string, strike: number, expiry_days = 30, opt_type = "call", iv = 0) =>
    get<unknown>(`/api/greeks?symbol=${symbol}&strike=${strike}&expiry_days=${expiry_days}&opt_type=${opt_type}&iv=${iv}`),
  fearGreed: () => get<{ score: number; label: string; color: string; components: unknown }>("/api/fear-greed"),
  snapshot: (symbols: string) => get<{ data: Record<string, unknown>; ts: number; count: number }>(`/api/snapshot?symbols=${encodeURIComponent(symbols)}`),
  sectorSpotlight: () => get<{ sectors: SectorSpotlight[]; ts: number }>("/api/sector/spotlight"),
};

export function fmt(n: number | undefined | null, dec = 2): string {
  if (n == null || isNaN(n)) return "—";
  return n.toLocaleString("en-IN", { minimumFractionDigits: dec, maximumFractionDigits: dec });
}

export function fmtCrore(n: number | undefined | null): string {
  if (n == null || isNaN(n)) return "—";
  if (n >= 1e7) return `₹${(n / 1e7).toFixed(2)}L Cr`;
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(2)} Cr`;
  return `₹${fmt(n)}`;
}

export function changeClass(n: number | undefined | null): string {
  if (n == null) return "neutral";
  return n > 0 ? "gain" : n < 0 ? "loss" : "neutral";
}

export function changeSign(n: number | undefined | null): string {
  if (n == null) return "";
  return n > 0 ? "+" : "";
}
