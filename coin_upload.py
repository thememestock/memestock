import os
import json
import httpx
from datetime import datetime
from dotenv import load_dotenv

# Load server environment keys
load_dotenv()

BASE_URL = os.getenv("NEXT_PUBLIC_APP_URL", "https://v0-meme-etf-dashboard.vercel.app")
COINS_API_URL = f"{BASE_URL}/api/coins"
KEEPER_API_KEY = os.getenv("KEEPER_API_KEY")

# 📋 Drop your target Solana contract addresses straight in here
CONTRACT_ADDRESSES = [
    "2zMMhcVQEXDtdE6vsFS7S7D5oUodfJHE8vd1gnBouauv",
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN",
    "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
    "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump",
    "Dz9mQ9NzkBcCsuGPFJ3r1bS4wgqKMHBPiVuniW8Mbonk",
    "2qEHjDLDLbuBgRYvsxhc5D6uDWAivNFZGan56P1tpump",
    "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
    "ED5nyyWEzpPPiWimP8vYm7sD7TD3LAt3Q3gRTWHzPJBY",
    "MEW1gQWJ3nEXg2qgERiKu7FAFj79PHvQVREQUzScPP5",
    "Ce2gx9KGXJ6C9Mp5b5x1sn9Mg87JwEbrQby4Zqo3pump",
    "63LfDmNb3MQ8mw9MtZ2To9bEA2M71kZUUGq5tiJxcqj9",
    "5z3EqYQo9HiCEs3R84RCDMu2n7anpDMxRhdK8PSWmrRC",
    "DtR4D9FtVoTX2569gaL837ZgrB6wNjj6tkmnX9Rdk9B2",
    "Cm6fNnMk7NfzStP9CZpsQA2v3jjzbcYGAxdJySmHpump",
    "HgBRWfYxEfvPhtqkaeymCQtHCrKE46qQ43pKe8HCpump",
    "y1AZt42vceCmStjW4zetK3VoNarC1VxJ5iDjpiupump",
    "eL5fUxj2J4CiQsmW85k5FG9DvuQjjUoBHoQBi2Kpump",
    "Df6yfrKC8kZE3KNkrHERKzAetSxbrWeniQfyJY4Jpump",
    "Bb4jR951QtVjeFAYFLBYXDSMKjbTDroCLPbFLdd7pump",
    "a3W4qutoEJA4232T2gwZUfgYJTetr96pU4SJMwppump",
    "A8C3xuqscfmyLrte3VmTqrAq8kgMASius9AFNANwpump",
    "3KHMZhpthXuiCcgfTv7vVu9PpEz64KAEURFwi6Lopump",
    "4Cnk9EPnW5ixfLZatCPJjDB1PUtcRpVVgTQukm9epump",
    "CB9dDufT3ZuQXqqSfa1c5kY935TEreyBw9XJXxHKpump",
    "C29ebrgYjYoJPMGPnPSGY1q3mMGk4iDSqnQeQQA7moon",
    "3TYgKwkE2Y3rxdw9osLRSpxpXmSC1C1oo19W9KHspump",
    "WENWENvqqNya429ubCdR81ZmD69brwQaaBYY6p3LCpk",
    "7BgBvyjrZX1YKz4oh9mjb8ZScatkkwb8DzFx7LoiVkM3",
    "H74CYmXgMkYHYuSRsZt6RJb4NYp2u72Vw8BS5huApump",
    "9AvytnUKsLxPxFHFqS6VLxaxt5p6BhYNr53SD2Chpump",
    "HtTYHz1Kf3rrQo6AqDLmss7gq5WrkWAaXn3tupUZbonk",
    "zGh48JtNHVBb5evgoZLXwgPD2Qu4MhkWdJLGDAupump",
    "6ogzHhzdrQr9Pgv6hZ2MNze7UrzBMAFyBBWUYp1Fhitx",
    "Hh3oTaqDCKKfdBgsQEvxp9sUwyNf8x9qmKqEMLBWpump",
    "HhJpBhRRn4g56VsyLuT8DL5Bv31HkXqsrahTTUCZeZg4",
    "DitHyRMQiSDhn5cnKMJV2CDDt6sVct96YrECiM49pump",
    "8Jx8AAHj86wbQgUTjGuj6GTTL5Ps3cqxKRTvpaJApump",
    "6yjNqPzTSanBWSa6dxVEgTjePXBrZ2FoHLDQwYwEsyM6",
    "H8xQ6poBjB9DTPMDTKWzWPrnxu4bDEhybxiouF8Ppump",
    "GkyPYa7NnCFbduLknCfBfP7p8564X1VZhwZYJ6CZpump",
    "ACtfUWtgvaXrQGNMiohTusi5jcx5RJf5zwu9aAxkpump",
    "8Ki8DpuWNxu9VsS3kQbarsCWMcFGWkzzA8pUPto9zBd5",
    "61Wj56QgGyyB966T7YsMzEAKRLcMvJpDbPzjkrCZc4Bi",
    "5LafQUrVco6o7KMz42eqVEJ9LW31StPyGjeeu5sKoMtA",
    "AywAYdNJnSLSXwKWYxDciPjqGRnwp4iZdQptuuQTpump",
    "kMKX8hBaj3BTRBbeYix9c16EieBP5dih8DTSSwCpump",
    "FtUEW73K6vEYHfbkfpdBZfWpxgQar2HipGdbutEhpump",
]


def sync_dex_to_coins_index():
    print("\n" + "=" * 80)
    print("🚀 INITIALIZING DEEPER V1 METADATA COINS PIPELINE SYNC")
    print("=" * 80)

    if not KEEPER_API_KEY:
        print("❌ ERROR: 'KEEPER_API_KEY' is missing from your local variables config.")
        return

    if not CONTRACT_ADDRESSES:
        print("⚠️  No contract addresses supplied inside the track list array.")
        return

    payload_coins = []

    print(f"📡 Querying separate token asset profiles sequentially...")
    print("-" * 80)

    try:
        with httpx.Client(timeout=15.0) as client:
            for ca in CONTRACT_ADDRESSES:
                # Target the dedicated v1 token pairs endpoint for Solana
                dex_endpoint = f"https://api.dexscreener.com/token-pairs/v1/solana/{ca}"

                try:
                    dex_response = client.get(dex_endpoint)
                    if dex_response.status_code != 200:
                        print(
                            f"⚠️  Skipping {ca[:6]}... — API Status: {dex_response.status_code}"
                        )
                        continue

                    pairs = dex_response.json()
                    if not pairs or not isinstance(pairs, list):
                        print(f"⚠️  No liquid trading pools found for CA: {ca[:8]}")
                        continue

                    # Target the primary pool row item
                    primary_pair = pairs[0]

                    base_token = primary_pair.get("baseToken", {})
                    ticker = base_token.get("symbol", "").replace("$", "")
                    name = base_token.get("name", "")

                    # Core market financial extractions
                    price_usd = (
                        float(primary_pair.get("priceUsd", 0.0))
                        if primary_pair.get("priceUsd")
                        else 0.0
                    )
                    market_cap = int(
                        primary_pair.get("marketCap", primary_pair.get("fdv", 0) or 0)
                    )
                    change_24h = (
                        float(primary_pair.get("priceChange", {}).get("h24", 0.0))
                        if primary_pair.get("priceChange")
                        else 0.0
                    )

                    # Extract the deeper social info array blocks
                    info = primary_pair.get("info", {}) or {}
                    logo_url = info.get("imageUrl", None)

                    twitter_url = None
                    socials_list = (
                        info.get("socials", []) if info.get("socials") else []
                    )
                    websites_list = (
                        info.get("websites", []) if info.get("websites") else []
                    )

                    # 🛡️ FIXED: Bulletproof support for both 'type' and 'platform' naming maps
                    for social in socials_list:
                        platform_name = str(
                            social.get("type", social.get("platform", ""))
                        ).lower()
                        if platform_name in ["twitter", "x"]:
                            twitter_url = social.get("url") or social.get("handle")
                            break

                    # Layer 2 Fallback: General link string matching
                    if not twitter_url:
                        for site in websites_list:
                            url_str = site.get("url", "").lower()
                            if "twitter.com" in url_str or "x.com" in url_str:
                                twitter_url = site.get("url")
                                break

                    print(
                        f"✨ Parsed [${ticker}] | MC: ${market_cap:,.0f} | Price: ${price_usd:.6f}"
                    )
                    print(
                        f"   └── X Link: {twitter_url if twitter_url else 'None available'}"
                    )

                    payload_coins.append(
                        {
                            "ticker": ticker,
                            "name": name,
                            "marketCap": market_cap,
                            "price": price_usd,
                            "change24h": change_24h,
                            "contractAddress": ca,
                            "twitter": twitter_url,
                            "logo": logo_url,
                        }
                    )

                except Exception as inner_err:
                    print(
                        f"❌ Failed to parse specific address token {ca[:8]}: {inner_err}"
                    )

            if not payload_coins:
                print("\n❌ Extraction loop produced zero matching token profiles.")
                return

            # Package into your exact camelCase POST endpoint contract envelope
            envelope = {"coins": payload_coins}
            headers = {
                "Authorization": f"Bearer {KEEPER_API_KEY}",
                "Content-Type": "application/json",
            }

            print("-" * 80)
            print(
                f"📡 Transmitting clean metadata array blocks to backend deployment..."
            )

            server_res = client.post(COINS_API_URL, json=envelope, headers=headers)

            if server_res.status_code in [200, 201]:
                print(f"\n⚡ [INDEX SYNC SUCCESS] Status: {server_res.status_code}")
                print(json.dumps(server_res.json(), indent=2))
            else:
                print(
                    f"\n⚠️  [SERVER DROPPED COINS SYNC - {server_res.status_code}]: {server_res.text}"
                )

    except Exception as err:
        print(f"❌ Pipeline failed: {err}")


if __name__ == "__main__":
    # print(len(CONTRACT_ADDRESSES))
    sync_dex_to_coins_index()
