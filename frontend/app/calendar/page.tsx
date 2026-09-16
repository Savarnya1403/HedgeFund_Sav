"use client";
import { useState, useEffect } from "react";

const API = "http://localhost:8001";
const IMPORTANCE_STYLE: Record<string, string> = {
  CRITICAL: "bg-red-900 text-red-300 border-red-700",
  HIGH: "bg-orange-900 text-orange-300 border-orange-700",
  MEDIUM: "bg-yellow-900 text-yellow-300 border-yellow-700",
  LOW: "bg-gray-800 text-gray-400 border-gray-700",
};
const TYPE_ICON: Record<string, string> = {
  MPC_MEETING: "🏦", FED_FOMC: "🇺🇸", GST_COUNCIL: "📋", UNION_BUDGET: "💰",
  INDIA_CPI: "📊", INDIA_WPI: "📊", INDIA_IIP: "🏭", INDIA_GDP: "📈",
  FNO_EXPIRY: "📅", FNO_MONTHLY_EXPIRY: "📅", EX_DIVIDEND: "💵",
  MARKET_HOLIDAY: "🏖️", INDEX_REBALANCE: "🔄", IPO_OPEN: "🚀",
};

function EventCard({ event }: { event: any }) {
  const style = IMPORTANCE_STYLE[event.importance ?? "LOW"] ?? IMPORTANCE_STYLE.LOW;
  const icon = TYPE_ICON[event.type] ?? "📌";
  return (
    <div className={`border rounded-lg p-4 ${style.split(" ").slice(2).join(" ")} bg-gray-900`}>
      <div className="flex items-start gap-3">
        <div className="text-2xl">{icon}</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className={`px-2 py-0.5 rounded text-xs font-bold border ${style}`}>{event.importance}</span>
            <span className="text-xs text-gray-500">{event.type?.replace(/_/g, " ")}</span>
          </div>
          <div className="text-sm font-medium text-gray-100">{event.description}</div>
          <div className="text-xs text-gray-400 mt-1">
            📅 {event.date} &nbsp;•&nbsp; {event.days_to_event === 0 ? "TODAY" : event.days_to_event === 1 ? "Tomorrow" : `${event.days_to_event} days away`}
          </div>
          {event.impact && <div className="text-xs text-blue-400 mt-1">Impact: {event.impact}</div>}
          {event.opportunity && <div className="text-xs text-green-400 mt-1">💡 {event.opportunity}</div>}
        </div>
      </div>
    </div>
  );
}

export default function CalendarPage() {
  const [calendar, setCalendar] = useState<any>(null);
  const [earnings, setEarnings] = useState<any[]>([]);
  const [dividends, setDividends] = useState<any[]>([]);
  const [ipos, setIpos] = useState<any[]>([]);
  const [tab, setTab] = useState("upcoming");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadAll = async () => {
      setLoading(true);
      try {
        const [cal, earn, div, ipo] = await Promise.allSettled([
          fetch(`${API}/api/calendar/events?days=60`).then(r => r.json()),
          fetch(`${API}/api/calendar/earnings`).then(r => r.json()),
          fetch(`${API}/api/calendar/dividends`).then(r => r.json()),
          fetch(`${API}/api/calendar/ipos`).then(r => r.json()),
        ]);
        if (cal.status === "fulfilled") setCalendar(cal.value);
        if (earn.status === "fulfilled") setEarnings(earn.value?.upcoming ?? earn.value ?? []);
        if (div.status === "fulfilled") setDividends(div.value ?? []);
        if (ipo.status === "fulfilled") setIpos(ipo.value ?? []);
      } catch { }
      setLoading(false);
    };
    loadAll();
  }, []);

  const criticalEvents = calendar?.critical_events ?? [];
  const next7 = calendar?.next_7_days ?? [];
  const allEvents = calendar?.events ?? [];

  return (
    <div className="min-h-screen bg-black text-white p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-1">Market Events Calendar</h1>
          <p className="text-gray-400">RBI MPC • Fed FOMC • Earnings • Dividends • F&O Expiry • Economic Data • IPOs • Index Rebalancing</p>
        </div>

        {loading && <div className="text-center py-20 text-gray-400">Loading calendar…</div>}

        {!loading && (
          <>
            {/* Critical alerts */}
            {criticalEvents.length > 0 && (
              <div className="bg-red-950 border border-red-700 rounded-xl p-4 mb-6">
                <div className="text-red-300 font-semibold text-sm mb-3">⚠️ Critical Upcoming Events</div>
                <div className="space-y-2">
                  {criticalEvents.map((e: any, i: number) => (
                    <div key={i} className="flex items-center gap-3 text-sm">
                      <span className="text-red-400 font-bold">{e.days_to_event === 0 ? "TODAY" : `${e.days_to_event}d`}</span>
                      <span className="text-red-200">{e.description}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Tabs */}
            <div className="flex gap-2 mb-6 border-b border-gray-800">
              {["upcoming","this_week","earnings","dividends","fno_expiry","ipos"].map(t => (
                <button key={t} onClick={() => setTab(t)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap ${tab === t ? "border-blue-500 text-white" : "border-transparent text-gray-400 hover:text-white"}`}>
                  {t.replace(/_/g," ").split(" ").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ")}
                </button>
              ))}
            </div>

            {tab === "upcoming" && (
              <div className="space-y-3">
                {allEvents.slice(0, 30).map((e: any, i: number) => <EventCard key={i} event={e} />)}
                {allEvents.length === 0 && <div className="text-center text-gray-500 py-10">No events found</div>}
              </div>
            )}

            {tab === "this_week" && (
              <div className="space-y-3">
                {next7.length > 0 ? next7.map((e: any, i: number) => <EventCard key={i} event={e} />) :
                  <div className="text-center text-gray-500 py-10">No events in next 7 days</div>}
              </div>
            )}

            {tab === "earnings" && (
              <div className="bg-gray-900 border border-gray-700 rounded-xl overflow-hidden">
                <div className="overflow-x-auto">
                <table className="w-full text-sm" style={{ minWidth: 560 }}>
                  <thead className="bg-gray-800 text-gray-400 text-xs">
                    <tr><th className="px-4 py-3 text-left">Company</th><th className="px-4 py-3 text-left">Symbol</th><th className="px-4 py-3 text-left">Earnings Date</th><th className="px-4 py-3 text-right">Days Away</th><th className="px-4 py-3 text-right">EPS Est</th><th className="px-4 py-3 text-right">Sector</th></tr>
                  </thead>
                  <tbody>
                    {earnings.map((e: any, i: number) => (
                      <tr key={i} className="border-t border-gray-800 hover:bg-gray-800/50">
                        <td className="px-4 py-3 text-gray-200">{e.company}</td>
                        <td className="px-4 py-3 text-blue-400 font-medium">{e.symbol}</td>
                        <td className="px-4 py-3 text-gray-300">{e.earnings_date}</td>
                        <td className={`px-4 py-3 text-right font-medium ${e.days_to_earnings <= 7 ? "text-orange-400" : "text-gray-300"}`}>
                          {e.days_to_earnings === 0 ? "TODAY" : e.days_to_earnings === 1 ? "Tomorrow" : `${e.days_to_earnings}d`}
                        </td>
                        <td className="px-4 py-3 text-right text-gray-300">{e.eps_estimate ? `₹${e.eps_estimate.toFixed(2)}` : "N/A"}</td>
                        <td className="px-4 py-3 text-right text-gray-400 text-xs">{e.sector}</td>
                      </tr>
                    ))}
                    {earnings.length === 0 && <tr><td colSpan={6} className="text-center py-10 text-gray-500">No upcoming earnings data</td></tr>}
                  </tbody>
                </table>
                </div>
              </div>
            )}

            {tab === "dividends" && (
              <div className="bg-gray-900 border border-gray-700 rounded-xl overflow-hidden">
                <div className="overflow-x-auto">
                <table className="w-full text-sm" style={{ minWidth: 600 }}>
                  <thead className="bg-gray-800 text-gray-400 text-xs">
                    <tr><th className="px-4 py-3 text-left">Company</th><th className="px-4 py-3 text-left">Symbol</th><th className="px-4 py-3 text-left">Ex-Date</th><th className="px-4 py-3 text-right">Days</th><th className="px-4 py-3 text-right">Amount</th><th className="px-4 py-3 text-right">Yield %</th><th className="px-4 py-3 text-left">Type</th></tr>
                  </thead>
                  <tbody>
                    {dividends.map((d: any, i: number) => (
                      <tr key={i} className="border-t border-gray-800 hover:bg-gray-800/50">
                        <td className="px-4 py-3 text-gray-200 text-xs">{d.company}</td>
                        <td className="px-4 py-3 text-blue-400 font-medium">{d.symbol}</td>
                        <td className="px-4 py-3 text-gray-300">{d.ex_date}</td>
                        <td className={`px-4 py-3 text-right font-medium ${d.days_to_ex_date <= 5 ? "text-orange-400" : "text-gray-300"}`}>{d.days_to_ex_date}d</td>
                        <td className="px-4 py-3 text-right text-green-400">{d.dividend_amount ? `₹${d.dividend_amount}` : "N/A"}</td>
                        <td className="px-4 py-3 text-right text-green-400">{d.dividend_yield_pct ? `${d.dividend_yield_pct.toFixed(2)}%` : "N/A"}</td>
                        <td className="px-4 py-3 text-gray-400 text-xs">{d.action_type}</td>
                      </tr>
                    ))}
                    {dividends.length === 0 && <tr><td colSpan={7} className="text-center py-10 text-gray-500">No upcoming dividends found</td></tr>}
                  </tbody>
                </table>
                </div>
              </div>
            )}

            {tab === "fno_expiry" && (
              <div className="space-y-6">
                <div className="bg-gray-900 border border-gray-700 rounded-xl p-4">
                  <h3 className="text-sm font-semibold text-gray-200 mb-4">Weekly Expiries (NIFTY)</h3>
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                    {allEvents.filter((e: any) => e.type === "FNO_EXPIRY" || e.type === "FNO_MONTHLY_EXPIRY").slice(0, 8).map((e: any, i: number) => (
                      <div key={i} className={`border rounded-lg p-3 text-center ${e.type === "FNO_MONTHLY_EXPIRY" ? "border-orange-700 bg-orange-950/30" : "border-gray-700 bg-gray-800"}`}>
                        <div className="text-xs text-gray-400">{e.type === "FNO_MONTHLY_EXPIRY" ? "Monthly" : "Weekly"}</div>
                        <div className="text-lg font-bold text-white mt-1">{e.date}</div>
                        <div className={`text-sm font-medium mt-1 ${e.days_to_event <= 3 ? "text-orange-400" : "text-gray-300"}`}>
                          {e.days_to_event === 0 ? "TODAY" : `${e.days_to_event} days`}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {tab === "ipos" && (
              <div className="space-y-4">
                {ipos.map((ipo: any, i: number) => (
                  <div key={i} className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="text-lg font-bold text-white">{ipo.company}</div>
                        <div className="text-sm text-gray-400 mt-1">Open: {ipo.open_date} → Close: {ipo.close_date}</div>
                        {ipo.listing_date && <div className="text-sm text-green-400">Listing: {ipo.listing_date}</div>}
                      </div>
                      <div className="text-right">
                        <div className="text-lg font-bold text-blue-400">
                          {ipo.issue_price_min && ipo.issue_price_max ? `₹${ipo.issue_price_min} - ₹${ipo.issue_price_max}` : ipo.issue_price ? `₹${ipo.issue_price}` : "Price TBA"}
                        </div>
                        {ipo.lot_size && <div className="text-xs text-gray-400 mt-1">Lot: {ipo.lot_size} shares</div>}
                        {ipo.listing_gain_pct != null && (
                          <div className={`text-sm font-bold mt-1 ${ipo.listing_gain_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                            Listing: {ipo.listing_gain_pct >= 0 ? "+" : ""}{ipo.listing_gain_pct?.toFixed(1)}%
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
                {ipos.length === 0 && <div className="text-center text-gray-500 py-10">No IPO data available</div>}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
