import json
import os
import sys
import requests
from datetime import datetime
from db import init_db, insert_combination

CONFIG_PATH = "config.json"


def load_config():
    with open(CONFIG_PATH) as f:
        config = json.load(f)
    # Allow environment variable to override config.json key (used by GitHub Actions)
    env_key = os.environ.get("SERPAPI_KEY")
    if env_key:
        config["serpapi_key"] = env_key
    return config


def parse_time(time_str):
    """Parse a time string like '9:05 PM' or '21:30' into a comparable datetime."""
    for fmt in ("%I:%M %p", "%H:%M"):
        try:
            return datetime.strptime(time_str.strip(), fmt)
        except ValueError:
            continue
    return None


def time_after(time_str, cutoff_str):
    """Return True if time_str is at or after cutoff_str (e.g. '16:30')."""
    t = parse_time(time_str)
    c = parse_time(cutoff_str)
    if t is None or c is None:
        return True  # if we can't parse, don't filter it out
    return t >= c


def extract_combinations(data, outbound_after=None):
    """
    Extract all outbound+return flight combinations from SerpAPI response.
    Each combination includes times, airlines, price, stops, duration.
    Filters outbound departures to only those at or after outbound_after (if set).
    """
    combinations = []
    all_flights = data.get("best_flights", []) + data.get("other_flights", [])

    for option in all_flights:
        legs = option.get("flights", [])
        if not legs:
            continue

        # Outbound leg (first flight in the option going TLS->MAD)
        outbound_leg = legs[0]
        outbound_dep = outbound_leg.get("departure_airport", {}).get("time", "")
        outbound_arr = outbound_leg.get("arrival_airport", {}).get("time", "")
        outbound_airline = outbound_leg.get("airline", "Unknown")

        # Filter by departure time if cutoff specified
        if outbound_after and outbound_dep:
            # SerpAPI returns times like "2026-10-08 21:30", extract HH:MM part
            time_part = outbound_dep.split(" ")[-1] if " " in outbound_dep else outbound_dep
            if not time_after(time_part, outbound_after):
                continue

        # Return leg info
        return_leg = legs[-1] if len(legs) > 1 else {}
        return_airline = return_leg.get("airline", outbound_airline)

        # Format times cleanly (extract HH:MM from "2026-10-08 21:30")
        def fmt_time(t):
            if not t:
                return "?"
            return t.split(" ")[-1] if " " in t else t

        outbound_time_clean = fmt_time(outbound_dep)
        return_arr_raw = return_leg.get("arrival_airport", {}).get("time", "") if return_leg else ""
        return_time_clean = fmt_time(return_arr_raw)

        stops = len(legs) - 1
        total_duration = str(option.get("total_duration", "?")) + " min"
        price = option.get("price")

        # Build a readable combination ID: out_time + out_airline + return_airline
        out_airline_short = outbound_airline[:3].upper()
        ret_airline_short = return_airline[:3].upper()
        combo_id = f"{outbound_time_clean}_{out_airline_short}_ret_{ret_airline_short}"

        combinations.append({
            "combination_id":   combo_id,
            "price":            price,
            "currency":         "EUR",
            "outbound_time":    outbound_time_clean,
            "outbound_airline": outbound_airline,
            "return_time":      return_time_clean,
            "return_airline":   return_airline,
            "stops":            stops,
            "total_duration":   total_duration,
        })

    # Sort by price
    combinations.sort(key=lambda x: x["price"] or float("inf"))
    return combinations


def fetch_all_combinations(api_key, flight):
    """Call SerpAPI and return all valid combinations for this flight config."""
    params = {
        "engine":        "google_flights",
        "departure_id":  flight["origin"],
        "arrival_id":    flight["destination"],
        "outbound_date": flight["outbound_date"],
        "return_date":   flight["return_date"],
        "currency":      "EUR",
        "hl":            "en",
        "api_key":       api_key,
        "type":          "1",  # round trip
    }

    try:
        response = requests.get("https://serpapi.com/search", params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        return None, str(e)

    outbound_after = flight.get("outbound_after")
    combinations = extract_combinations(data, outbound_after)

    if not combinations:
        return None, "No matching combinations found (check outbound_after filter)"

    return combinations, None


def run():
    config = load_config()
    api_key = config.get("serpapi_key", "")

    if not api_key or api_key == "YOUR_SERPAPI_KEY_HERE":
        print("ERROR: Please set your SerpAPI key in config.json or as SERPAPI_KEY environment variable")
        sys.exit(1)

    init_db()

    for flight in config["flights"]:
        flight_id = flight["id"]
        label = flight["label"]
        print(f"\nFetching: {label}")
        print(f"  Outbound filter: depart after {flight.get('outbound_after', 'any time')}")

        combinations, error = fetch_all_combinations(api_key, flight)

        if error:
            print(f"  FAILED -- {error}")
            insert_combination(flight_id, "ERROR", None, None,
                               None, None, None, None, None, None, error=error)
            continue

        print(f"  Found {len(combinations)} combination(s):")
        for c in combinations:
            print(f"    [{c['combination_id']}] "
                  f"Out {c['outbound_time']} ({c['outbound_airline']}) | "
                  f"Ret arr {c['return_time']} ({c['return_airline']}) | "
                  f"EUR{c['price']} | {c['stops']} stop(s) | {c['total_duration']}")
            insert_combination(
                flight_id,
                c["combination_id"],
                c["price"],
                c["currency"],
                c["outbound_time"],
                c["outbound_airline"],
                c["return_time"],
                c["return_airline"],
                c["stops"],
                c["total_duration"],
            )

    print("\nDone. Run export.py to refresh your Excel dashboard.")


if __name__ == "__main__":
    run()
