import time
import httpx


def get_ca_from_dex_search(client: httpx.Client, name: str) -> str:
    """Queries DexScreener to accurately resolve the on-chain Solana Contract Address."""
    url = f"https://api.dexscreener.com/latest/dex/search?q={name}"
    try:
        res = client.get(url, timeout=5.0)
        if res.status_code == 200:
            data = res.json()
            pairs = data.get("pairs", [])

            # Filter specifically for Solana liquidity pools
            sol_pairs = [p for p in pairs if p.get("chainId") == "solana"]
            if sol_pairs:
                # Extract the base token address (the actual CA of the meme coin)
                return sol_pairs[0].get("baseToken", {}).get("address", "Unknown")
    except Exception:
        pass
    return "Not Found"


def get_top_100_sol_memes_with_cas():
    # Ask the user if they want to proceed with full CA extraction
    user_choice = (
        input("Do you want to extract on-chain Contract Addresses (CAs)? (y/n): ")
        .strip()
        .lower()
    )
    extract_cas = user_choice in ["y", "yes"]

    # 1. Fetch Top 100 Solana Meme Coins ordered by Market Cap
    gecko_url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "category": "solana-meme-coins",
        "order": "market_cap_desc",
        "per_page": 100,
        "page": 1,
        "sparkline": "false",
    }

    print("\n🚀 Fetching market cap rankings from CoinGecko...")

    with httpx.Client() as client:
        response = client.get(gecko_url, params=params)

        if response.status_code != 200:
            print(f"❌ Error fetching from CoinGecko: {response.text}")
            return

        tokens = response.json()

        if extract_cas:
            print(
                f"\n✨ Found {len(tokens)} tokens. Starting dynamic CA lookups with 0.5s intervals...\n"
            )
            print(
                f"{'#':<4} | {'Ticker':<10} | {'Name':<20} | {'Market Cap':<15} | {'Contract Address (CA)'}"
            )
        else:
            print(f"\n✨ Found {len(tokens)} tokens. Fast dumping basic metadata...\n")
            print(
                f"{'#':<4} | {'Ticker':<10} | {'Name':<20} | {'Market Cap':<15} | {'CoinGecko ID'}"
            )

        print("-" * 105)

        # 2. Iterate through tokens and output data framing
        for idx, token in enumerate(tokens, 1):
            ticker = token.get("symbol", "").upper()
            name = token.get("name", "")
            market_cap = f"${token.get('market_cap', 0):,}"
            token_id = token.get("id", "")

            if extract_cas:
                # Execute live lookup on DexScreener
                ca = get_ca_from_dex_search(client, name)
                print(f"{idx:<4} | {ticker:<10} | {name:<20} | {market_cap:<15} | {ca}")
                # Enforce the requested 0.5s safety gap to handle potential rate limits
                time.sleep(0.5)
            else:
                # Skip network lookup and immediately print the row with the standard ID
                print(
                    f"{idx:<4} | {ticker:<10} | {name:<20} | {market_cap:<15} | {token_id}"
                )


if __name__ == "__main__":
    start_time = time.time()
    get_top_100_sol_memes_with_cas()
    print(f"\n📊 Run Completed in {((time.time() - start_time) / 60):.2f} minutes!")
