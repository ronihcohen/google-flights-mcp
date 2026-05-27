# google-flights-mcp

An MCP server that searches Google Flights using a headless Firefox browser and returns structured flight results to Claude agents.

## What it does

Exposes a single MCP tool — `search_google_flights` — that drives a real browser against `google.com/travel/flights` and returns the cheapest fare plus a list of flight options (airline, departure/arrival times, duration, stops, price).

## Tool

```
search_google_flights(origin, destination, depart_date, return_date?)
```

| Parameter | Type | Example |
|---|---|---|
| `origin` | IATA code | `"TLV"` |
| `destination` | IATA code | `"FCO"` |
| `depart_date` | `YYYY-MM-DD` | `"2026-06-07"` |
| `return_date` | `YYYY-MM-DD` or `""` | `"2026-06-14"` (omit for one-way) |

Returns JSON with `cheapest_fare`, `result_count`, and a `flights` list.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install fastmcp playwright
playwright install firefox
```

## Running

```bash
python mcp_server.py
```

Or via `.mcp.json` — Claude Code picks it up automatically when you open this project.
