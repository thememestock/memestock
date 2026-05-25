import os
import json
import time
import httpx
from datetime import datetime
from dotenv import load_dotenv

# Load server environment keys
load_dotenv()

BASE_URL = os.getenv("NEXT_PUBLIC_APP_URL", "https://v0-meme-etf-dashboard.vercel.app")
COINS_API_URL = f"{BASE_URL}/api/coins"
KEEPER_API_KEY = os.getenv("KEEPER_API_KEY")


def execute_pricing_sync_cycle():
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n⏰ [{timestamp}] FETCHING INDEX METRICS FROM DATABASE...")

    headers = {
        "Authorization": f"Bearer {KEEPER_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            # 📦 Step 1: Pull the coins list framework from your API
            coins_res = client.get(COINS_API_URL)
            if coins_res.status_code != 200:
                print(
                    f"   ❌ Failed to pull coin framework from server: {coins_res.status_code}"
                )
                return

            coins_data = coins_res.json().get("data", [])
            if not coins_data:
                print("   ⚠️  No verified coins found in database. Skipping cycle.")
                return

            # Map addresses to internal UUIDs for quick matching
            contract_to_coin_id = {}
            valid_cas = []

            for c in coins_data:
                ca = c.get("contract_address") or c.get("contractAddress")
                if ca:
                    valid_cas.append(ca)
                    contract_to_coin_id[ca.lower()] = c.get("id")

            if not valid_cas:
                print(
                    "   ⚠️  Active coins exist, but none have configured contract addresses."
                )
                return

            # 🧩 Step 2: Chunk addresses into maximum batches of 30 items
            MAX_BATCH_SIZE = 30
            coin_updates = []
            processed_cas = set()

            print(
                f"   📦 Total index token count: {len(valid_cas)}. Splitting queries..."
            )

            for i in range(0, len(valid_cas), MAX_BATCH_SIZE):
                chunk = valid_cas[i : i + MAX_BATCH_SIZE]
                cas_string = ",".join(chunk)
                dex_endpoint = (
                    f"https://api.dexscreener.com/tokens/v1/solana/{cas_string}"
                )

                try:
                    dex_res = client.get(dex_endpoint)
                    if dex_res.status_code != 200:
                        print(
                            f"   ⚠️  DEX Screener batch query failed for chunk index {i}. Skipping subset."
                        )
                        continue

                    raw_dex_data = dex_res.json()
                    pairs = (
                        raw_dex_data
                        if isinstance(raw_dex_data, list)
                        else raw_dex_data.get("pairs", [])
                    )

                    if not pairs:
                        continue

                    # Parse out current chunk tokens
                    for pair in pairs:
                        base_token = pair.get("baseToken", {})
                        ca_lower = base_token.get("address", "").lower()

                        if (
                            not ca_lower
                            or ca_lower in processed_cas
                            or ca_lower not in contract_to_coin_id
                        ):
                            continue

                        coin_id = contract_to_coin_id[ca_lower]
                        ticker = base_token.get("symbol", "").replace("$", "")

                        price_usd = (
                            float(pair.get("priceUsd", 0.0))
                            if pair.get("priceUsd")
                            else 0.0
                        )
                        market_cap = int(pair.get("marketCap", pair.get("fdv", 0) or 0))
                        change_24h = (
                            float(pair.get("priceChange", {}).get("h24", 0.0))
                            if pair.get("priceChange")
                            else 0.0
                        )

                        processed_cas.add(ca_lower)

                        coin_updates.append(
                            {
                                "id": coin_id,
                                "ticker": ticker,
                                "price": price_usd,
                                "marketCap": market_cap,
                                "change24h": change_24h,
                            }
                        )
                except Exception as chunk_err:
                    print(f"   ❌ Failed to process batch at offset {i}: {chunk_err}")

            # 🚀 Step 3: Dispatch aggregated metrics payload via Next.js PATCH execution
            if not coin_updates:
                print("   ⚠️  No matching pair metrics parsed from data streams.")
                return

            patch_payload = {"updates": coin_updates}
            patch_res = client.patch(COINS_API_URL, json=patch_payload, headers=headers)

            if patch_res.status_code == 200:
                print(
                    f"   ⚡ [PRICE TICK SYNCED] Successfully refreshed {len(coin_updates)} index tokens across all chunks."
                )
                for update in coin_updates:
                    print(
                        f"       └── ${update['ticker']}: ${update['price']:.6f} | MCAP: ${update['marketCap']:,}"
                    )
            else:
                print(f"   ⚠️  Server rejected partial updates array: {patch_res.text}")

    except Exception as err:
        print(f"   ❌ Sync runtime error: {err}")


def initialize_pricing_loop():
    if not KEEPER_API_KEY:
        print(
            "❌ CRITICAL ERROR: 'KEEPER_API_KEY' is missing from your local environment setup."
        )
        return

    print(
        "================================================================================"
    )
    print(
        "🦅 RE-PRICE RUNTIME KEEPER NOW OPERATIONALLY ACTIVE (SCALABLE BATCHING MODE)"
    )
    print("🛸 Frequency Status: Strictly polling changes every 30 seconds.")
    print(
        "================================================================================"
    )

    while True:
        execute_pricing_sync_cycle()
        time.sleep(30)


if __name__ == "__main__":
    initialize_pricing_loop()
