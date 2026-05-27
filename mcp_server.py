"""MCP server exposing search_flights as a tool for Claude agents."""

import json
import sys
from pathlib import Path

# Ensure the lib next to this file is importable regardless of cwd
sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.fastmcp import FastMCP
from search_flights_lib import _run_search

mcp = FastMCP("flights")


@mcp.tool()
async def search_google_flights(
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str = "",
) -> str:
    """Search Google Flights and return the cheapest fare with a list of options.

    Drives a real headless Firefox browser against google.com/travel/flights.
    No screenshots are saved (agent-safe, no disk bloat).

    Args:
        origin: IATA airport code for the departure airport, e.g. "TLV", "LAX", "JFK".
        destination: IATA airport code for the arrival airport, e.g. "FCO", "SFO", "CDG".
        depart_date: Departure date in YYYY-MM-DD format, e.g. "2026-06-07".
        return_date: Return date in YYYY-MM-DD format for round trips, e.g. "2026-06-14".
            Pass an empty string "" for a one-way search.

    Returns:
        JSON string with cheapest_fare, result_count, and a flights list
        (each entry has airline, departs, arrives, duration, stops, price).
    """
    result = await _run_search(
        origin=origin,
        destination=destination,
        depart_date=depart_date,
        return_date=return_date,
        save_screenshots=False,
        run_dir=None,
    )
    # Return a clean summary (drop raw text to keep the response concise)
    output = {
        "origin": result["origin"],
        "destination": result["destination"],
        "depart_date": result["depart_date"],
        "return_date": result["return_date"],
        "cheapest_fare": result["cheapest_fare"],
        "result_count": result["result_count"],
        "flights": [
            {k: v for k, v in f.items() if k != "raw"}
            for f in result["flights"]
        ],
    }
    return json.dumps(output, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run()
