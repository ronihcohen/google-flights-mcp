"""Core search_flights implementation — importable by the MCP server or scripts."""

import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


def _iso_to_mmddyyyy(date_str: str) -> str:
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%m/%d/%Y")


def _month_day(date_str: str) -> tuple[str, str]:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.strftime("%b"), str(dt.day)


def _parse_flights(raw_texts: list[str], origin: str, destination: str) -> list[dict]:
    flights = []
    for raw in raw_texts:
        lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
        if len(lines) < 4:
            continue
        flight: dict = {"raw": " | ".join(lines)}
        # Time range: "5:54 PM – 7:36 PM" (any dash/en-dash/em-dash variant)
        time_match = re.search(r"(\d{1,2}:\d{2}\s*[AP]M)\s*[–—\-]\s*(\d{1,2}:\d{2}\s*[AP]M)", raw)
        if time_match:
            flight["departs"] = time_match.group(1)
            flight["arrives"] = time_match.group(2)
        # Duration: "1 hr 42 min" or "3 hr"
        dur_match = re.search(r"(\d+ hr(?:\s+\d+ min)?)", raw)
        if dur_match:
            flight["duration"] = dur_match.group(1)
        # Stops
        if "Nonstop" in raw:
            flight["stops"] = "Nonstop"
        else:
            stop_match = re.search(r"(\d+)\s+stop", raw)
            flight["stops"] = f"{stop_match.group(1)} stop(s)" if stop_match else "unknown"
        # Price: ₪1,234 or $123 etc.
        price_match = re.search(r"([₪$€£¥]\d[\d,]+)", raw)
        if price_match:
            flight["price"] = price_match.group(1)
        # Airline: first short line that isn't a time/price/number
        for ln in lines:
            if ln and not re.match(r"^[\d₪$€£¥\+\-]", ln) and "stop" not in ln.lower() \
                    and "hr" not in ln and "min" not in ln and "CO2" not in ln \
                    and "emissions" not in ln and "Nonstop" not in ln \
                    and origin not in ln and destination not in ln:
                flight["airline"] = ln
                break
        flights.append(flight)
    return flights


async def _run_search(
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str,
    save_screenshots: bool,
    run_dir: Optional[Path],
) -> dict:
    from playwright.async_api import async_playwright

    if save_screenshots and run_dir:
        screenshots_dir = run_dir / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        log_path = run_dir / "final_script_log.txt"
        log_path.write_text("")
    else:
        screenshots_dir = None
        log_path = None

    messages: list[str] = []

    def log(step: int, msg: str) -> None:
        line = f"step {step} action: {msg}"
        messages.append(line)
        if log_path:
            with log_path.open("a") as f:
                f.write(line + "\n")

    def screenshot(page, name: str):
        if save_screenshots and screenshots_dir:
            return page.screenshot(path=str(screenshots_dir / name))
        return asyncio.sleep(0)  # no-op coroutine

    dep_mmddyyyy = _iso_to_mmddyyyy(depart_date)
    dep_mon, dep_day = _month_day(depart_date)
    is_round_trip = bool(return_date)
    ret_mmddyyyy = _iso_to_mmddyyyy(return_date) if is_round_trip else None
    ret_mon, ret_day = (_month_day(return_date) if is_round_trip else (None, None))

    if log_path:
        with log_path.open("a") as f:
            f.write(
                f"step 0 params: origin={origin} destination={destination}"
                f" depart_date={depart_date} return_date={return_date}\n"
            )

    async with async_playwright() as pw:
        browser = await pw.firefox.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 1800})
        page = await context.new_page()

        await page.goto("https://www.google.com/travel/flights", wait_until="domcontentloaded")
        await asyncio.sleep(3)
        await screenshot(page, "final_execution_1_open_start_page.png")
        log(1, "opened Google Flights homepage")

        # Switch to one-way if no return date
        if not is_round_trip:
            trip_combo = page.get_by_role("combobox").filter(has_text="Round trip")
            if await trip_combo.count() > 0:
                await trip_combo.click()
                await asyncio.sleep(1)
                oneway_opt = page.get_by_role("option", name="One way")
                if await oneway_opt.count() > 0:
                    await oneway_opt.click()
                    await asyncio.sleep(1)
                    log(1, "switched to one-way mode")

        # Origin
        origin_input = page.locator("input[aria-label='Where from?']")
        await origin_input.click()
        await asyncio.sleep(1)
        await page.keyboard.press("Control+a")
        await asyncio.sleep(0.2)
        await page.keyboard.press("Backspace")
        await asyncio.sleep(0.3)
        for ch in origin:
            await page.keyboard.press(ch)
            await asyncio.sleep(0.15)
        await asyncio.sleep(2)
        await page.get_by_role("option").first.click()
        await asyncio.sleep(1.5)
        await screenshot(page, "final_execution_2_origin_set.png")
        log(2, f"set origin to {origin}")

        # Destination
        dest_input = page.locator("input[aria-label='Where to? ']")
        await dest_input.click()
        await asyncio.sleep(1)
        for ch in destination:
            await page.keyboard.press(ch)
            await asyncio.sleep(0.15)
        await asyncio.sleep(2)
        await page.get_by_role("option").first.click()
        await asyncio.sleep(1.5)
        await screenshot(page, "final_execution_3_destination_set.png")
        log(3, f"set destination to {destination}")

        # Departure date
        await page.locator("input[aria-label='Departure']").first.click()
        await asyncio.sleep(2)
        dep_textbox = page.get_by_role("dialog").locator("input[placeholder='Departure']").first
        await dep_textbox.click()
        await asyncio.sleep(0.5)
        await dep_textbox.type(dep_mmddyyyy, delay=80)
        await asyncio.sleep(1)
        log(4, f"typed departure date {dep_mmddyyyy}")

        # Return date
        if is_round_trip:
            await page.keyboard.press("Tab")
            await asyncio.sleep(1)
            await page.keyboard.type(ret_mmddyyyy, delay=80)
            await asyncio.sleep(1)
            await page.keyboard.press("Enter")
            await asyncio.sleep(1.5)
            log(5, f"typed return date {ret_mmddyyyy}")
        else:
            await page.keyboard.press("Enter")
            await asyncio.sleep(1.5)
            log(5, "one-way trip — no return date")

        done_btn = page.get_by_role("button", name="Done")
        if await done_btn.count() > 0:
            await done_btn.click()
            await asyncio.sleep(1.5)

        form_snap = await page.get_by_role("search").aria_snapshot()
        dep_ok = dep_mon in form_snap and dep_day in form_snap
        ret_ok = (ret_mon in form_snap and ret_day in form_snap) if is_round_trip else True
        log(6, f"form state: dep='{dep_mon} {dep_day}' ok={dep_ok}, ret ok={ret_ok}")

        await screenshot(page, "final_execution_4_form_filled.png")

        # Search
        await page.get_by_role("button", name="Search").click()
        await asyncio.sleep(6)
        log(7, "clicked Search — waiting for results")
        await screenshot(page, "final_execution_5_results_page.png")

        result_count = 0
        alert = page.get_by_role("alert").filter(has_text="results returned")
        if await alert.count() > 0:
            alert_text = await alert.first.inner_text()
            log(7, f"results alert: {alert_text}")
            count_match = re.search(r"(\d+)", alert_text)
            if count_match:
                result_count = int(count_match.group(1))

        # Cheapest price tab
        cheapest_price = ""
        cheapest_tab = page.get_by_role("tab").filter(has_text="Cheapest")
        if await cheapest_tab.count() > 0:
            cheapest_price = (await cheapest_tab.inner_text()).strip()
            cheapest_price = cheapest_price.replace("Cheapest\nfrom ", "").replace("Cheapest", "").strip()

        log(8, f"cheapest price from tab: {cheapest_price!r}")

        # Extract flight listings
        raw_flights = []
        listitems = await page.get_by_role("listitem").all()
        for item in listitems:
            try:
                text = await item.inner_text()
                # Flight rows contain a time range and a price; filter out nav/UI items
                has_time = bool(re.search(r"\d{1,2}:\d{2}\s*[AP]M", text))
                has_price = bool(re.search(r"[₪$€£¥]\d[\d,]+", text))
                if has_time and has_price and len(text) > 20:
                    raw_flights.append(text.strip())
            except Exception:
                pass

        log(8, f"found {len(raw_flights)} flight listings")
        await screenshot(page, "final_execution_6_results_detail.png")

        flights = _parse_flights(raw_flights, origin, destination)

        final_datum = cheapest_price if cheapest_price else f"{result_count} results — see screenshot"
        log(9, f"final datum — cheapest fare: {final_datum}")

        if log_path:
            with log_path.open("a") as f:
                f.write(f"\nFINAL_RESPONSE: Cheapest fare for {origin}→{destination}"
                        f" ({depart_date} → {return_date or 'one-way'}): {final_datum}\n")

        await browser.close()

    return {
        "origin": origin,
        "destination": destination,
        "depart_date": depart_date,
        "return_date": return_date,
        "cheapest_fare": final_datum,
        "result_count": result_count,
        "flights": flights,
        "log": messages,
    }


def search_flights(
    origin: str = "LAX",
    destination: str = "SFO",
    depart_date: str = "2026-06-07",
    return_date: str = "2026-06-14",
    save_screenshots: bool = False,
    run_dir: Optional[str] = None,
) -> dict:
    """Search Google Flights for the cheapest ticket between two airports.

    Args:
        origin: IATA airport code for departure; 3-letter uppercase. Default: "LAX".
        destination: IATA airport code for arrival; 3-letter uppercase. Default: "SFO".
        depart_date: Departure date in YYYY-MM-DD format. Default: "2026-06-07".
        return_date: Return date in YYYY-MM-DD format; empty string for one-way.
            Default: "2026-06-14".
        save_screenshots: Save browser screenshots to run_dir for debugging.
            Default: False (skip screenshots — use this in agent/MCP contexts).
        run_dir: Directory to save screenshots and log; only used when
            save_screenshots=True. Default: None.

    Returns:
        dict with keys:
            ``origin``, ``destination``, ``depart_date``, ``return_date`` (str),
            ``cheapest_fare`` (str), ``result_count`` (int),
            ``flights`` (list of dicts with airline, departs, arrives, duration,
            stops, price, raw), ``log`` (list of step strings).
    """
    run_path = Path(run_dir) if run_dir else None
    return asyncio.run(
        _run_search(origin, destination, depart_date, return_date, save_screenshots, run_path)
    )
