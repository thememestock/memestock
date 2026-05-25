import os
import sys
import json
import random
import httpx
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from solana.rpc.api import Client

# Load local environment settings (.env file)
load_dotenv()

# Network Profiles Configuration
BASE_URL = os.getenv("NEXT_PUBLIC_APP_URL", "http://localhost:3000")
COINS_ENDPOINT = f"{BASE_URL}/api/coins"
AIRDROPS_ENDPOINT = f"{BASE_URL}/api/airdrops"
SOLANA_RPC_URL = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")


def schedule_provably_fair_airdrops(block_number: int, base_delay_minutes: int):
    """
    Fetches the block hash for a given block number, uses it as a deterministic
    seed to pick 3 random coins, and schedules them sequentially.
    """
    api_key = os.getenv("KEEPER_API_KEY")
    if not api_key:
        print(
            "❌ ERROR: 'KEEPER_API_KEY' variable not found in your environment (.env)."
        )
        return

    auth_headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # =====================================================================
    # 🔗 STEP 1: FETCH BLOCK HASH FROM SOLANA RPC
    # =====================================================================
    print(f"\n🔗 Querying Solana RPC for Block #{block_number}...")
    try:
        solana_client = Client(SOLANA_RPC_URL)
        # max_supported_transaction_version=0 is required for modern Solana blocks
        block_res = solana_client.get_block(
            block_number, max_supported_transaction_version=0
        )

        if not block_res.value:
            print(
                f"❌ Block {block_number} not found or was skipped. Try a more recent block."
            )
            return

        block_hash = str(block_res.value.blockhash)
        print(f"✅ Block Hash Retrieved: {block_hash}")
    except Exception as e:
        print(f"❌ Failed to fetch block hash. RPC Error: {e}")
        return

    # =====================================================================
    # 📡 STEP 2: PULL ACTIVE INDEX COINS
    # =====================================================================
    print(f"📡 Querying public token matrix from: {COINS_ENDPOINT}...")
    try:
        with httpx.Client(timeout=10.0) as client:
            coins_response = client.get(COINS_ENDPOINT)
            if coins_response.status_code != 200:
                print(
                    f"❌ Failed to fetch assets index. Server responded with: {coins_response.status_code}"
                )
                return

            coin_pool = coins_response.json().get("data", [])
            if len(coin_pool) < 3:
                print(
                    "⚠️ Database coin registry has fewer than 3 coins. Add more to the index first."
                )
                return
            print(f"📊 Extracted {len(coin_pool)} verified index assets.")

    except Exception as e:
        print(f"❌ Connection to endpoint failed: {e}")
        return

    # =====================================================================
    # 🎲 STEP 3: SEED RANDOMIZER & SELECT 3 COINS
    # =====================================================================
    print(f"\n🎰 Seeding Roulette Wheel with Block Hash...")
    random.seed(block_hash)

    # Pick 3 unique coins deterministically based on the seed
    selected_coins = random.sample(coin_pool, 3)

    print("🎯 SELECTED TARGETS FOR UPCOMING WAVES:")
    for idx, c in enumerate(selected_coins):
        print(f"   {idx+1}. ${c['ticker']} ({c['name']})")

    # =====================================================================
    # 🔒 STEP 4: STITCH PAYLOADS AND PUSH TO API
    # =====================================================================
    print(f"\n🔒 Authorizing transaction... Pushing scheduled drops to the ledger.")

    with httpx.Client(timeout=15.0) as client:
        for i, coin in enumerate(selected_coins):
            # Space the airdrops out slightly (e.g., 5 mins, 10 mins, 15 mins)
            # so the dispatcher daemon has time to cleanly process each one.
            offset_minutes = base_delay_minutes + (i * 5)

            future_time = datetime.now(timezone.utc) + timedelta(minutes=offset_minutes)
            iso_timestamp_str = future_time.strftime("%Y-%m-%dT%H:%M:%SZ")

            airdrop_payload = {
                "action": "schedule",
                "scheduledAt": iso_timestamp_str,
                "coinTicker": coin["ticker"],
                "coinName": coin["name"],
                "coinLogo": coin.get("logo", "🎯"),
                "coinContractAddress": coin["contract_address"],
                # Append the transparent verifiability proofs:
                "blockNumber": block_number,
                "blockHash": block_hash,
            }

            try:
                response = client.post(
                    AIRDROPS_ENDPOINT, json=airdrop_payload, headers=auth_headers
                )

                if response.status_code in [200, 201]:
                    print(
                        f"   ✅ [SYNCED] Wave {i+1}: ${coin['ticker']} scheduled for {iso_timestamp_str}"
                    )
                else:
                    print(
                        f"   ⚠️ [REJECTED] ${coin['ticker']} - Status {response.status_code}: {response.text}"
                    )

            except Exception as e:
                print(f"   ❌ Failed to broadcast payload for ${coin['ticker']}: {e}")

    print("\n🎉 All transparent schedules locked in.")


if __name__ == "__main__":
    print(
        "================================================================================"
    )
    print("🛠️  MEMECOIN PROVABLY FAIR SCHEDULER DAEMON")
    print(
        "================================================================================"
    )

    try:
        target_block = int(
            input("🔢 Enter a recent Solana Block Number to use as seed: ")
        )
    except ValueError:
        print("❌ Invalid input. Must be a numeric block number.")
        sys.exit(1)

    # Base delay until the first drop hits (the subsequent ones will be +5 mins each)
    TEST_COUNTDOWN_OFFSET_MINUTES = 5

    schedule_provably_fair_airdrops(
        block_number=target_block, base_delay_minutes=TEST_COUNTDOWN_OFFSET_MINUTES
    )
