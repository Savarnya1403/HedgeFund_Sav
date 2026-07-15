import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

function err(msg: string, status = 500) {
  return NextResponse.json({ error: msg }, { status });
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const type = searchParams.get("type");
  const symbol = searchParams.get("symbol")?.toUpperCase();

  if (!type) return err("Missing type", 400);

  try {
    const { NseIndia } = await import("stock-nse-india");
    const nse = new NseIndia();

    switch (type) {
      case "equity":
        if (!symbol) return err("Missing symbol", 400);
        return NextResponse.json(await nse.getEquityDetails(symbol));

      case "trade-info":
        if (!symbol) return err("Missing symbol", 400);
        return NextResponse.json(await nse.getEquityTradeInfo(symbol));

      case "corporate-info":
        if (!symbol) return err("Missing symbol", 400);
        return NextResponse.json(await nse.getEquityCorporateInfo(symbol));

      case "intraday":
        if (!symbol) return err("Missing symbol", 400);
        return NextResponse.json(await nse.getEquityIntradayData(symbol));

      case "option-chain":
        if (!symbol) return err("Missing symbol", 400);
        return NextResponse.json(await nse.getEquityOptionChain(symbol));

      case "index-option-chain": {
        const idx = symbol || "NIFTY";
        return NextResponse.json(await nse.getIndexOptionChain(idx));
      }

      case "all-indices":
        return NextResponse.json(await nse.getAllIndices());

      case "market-status":
        return NextResponse.json(await nse.getMarketStatus());

      case "market-turnover":
        return NextResponse.json(await nse.getMarketTurnover());

      case "pre-open":
        return NextResponse.json(await nse.getPreOpenMarketData());

      case "circulars":
        return NextResponse.json(await nse.getCirculars());

      case "daily-reports":
        return NextResponse.json(await nse.getMergedDailyReportsCapital());

      case "technical":
        if (!symbol) return err("Missing symbol", 400);
        return NextResponse.json(await nse.getTechnicalIndicators(symbol));

      case "history": {
        if (!symbol) return err("Missing symbol", 400);
        const days = parseInt(searchParams.get("days") || "90", 10);
        const end = new Date();
        const start = new Date();
        start.setDate(start.getDate() - days);
        const data = await nse.getEquityHistoricalData(symbol, { start, end });
        const rows: unknown[] = [];
        for (const chunk of data) {
          if (Array.isArray((chunk as { data?: unknown[] }).data)) {
            rows.push(...((chunk as { data: unknown[] }).data));
          }
        }
        return NextResponse.json(rows);
      }

      default:
        return err(`Unknown type: ${type}`, 400);
    }
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    console.error(`NSE route error [${type}]:`, msg);
    return err(msg);
  }
}
