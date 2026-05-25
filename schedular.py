import os
import json
import random
import httpx
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

# Load local environment settings (.env file)
load_dotenv()

# Network Profiles Configuration
BASE_URL = os.getenv("NEXT_PUBLIC_APP_URL")
COINS_ENDPOINT = f"{BASE_URL}/api/coins"
AIRDROPS_ENDPOINT = f"{BASE_URL}/api/airdrops"


def schedule_next_roulette_target(delay_minutes: int):
    """
    Automated scheduling sub-unit. Extracts options from the public coin index,
    picks a random target, calculates a future timestamp, and securely registers
    it with the protected Next.js router.
    """
    # Grab the newly configured environment token variable
    api_key = os.getenv("KEEPER_API_KEY")
    if not api_key:
        print(
            "❌ ERROR: 'KEEPER_API_KEY' variable not found in your environment (.env)."
        )
        return

    # Set up auth headers using your required Bearer pattern
    authenticated_headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    print(f"📡 Querying public token matrix from: {COINS_ENDPOINT}...")

    with httpx.Client() as client:
        # Step 1: Pull available coin variants from the index database (Public GET)
        try:
            coins_response = client.get(COINS_ENDPOINT)
            if coins_response.status_code != 200:
                print(
                    f"❌ Failed to fetch assets index. Server responded with: {coins_response.status_code}"
                )
                return

            coins_payload = coins_response.json()
            coin_pool = coins_payload.get("data", [])

            if not coin_pool:
                print(
                    "⚠️  Database coin registry is empty. Sync tokens into your index table first."
                )
                return

            print(f"📊 Extracted {len(coin_pool)} verified index assets from pool.")

        except Exception as e:
            print(f"❌ Connection to endpoint failed during fetch phase: {e}")
            return

        # Step 2: Spin the roulette wheel to select an asset profile
        selected_coin = random.choice(coin_pool)
        print(
            f"🎡 Wheel selection confirmed: ${selected_coin['ticker']} ({selected_coin['name']})"
        )

        # Step 3: Compute precision upcoming execution windows (ISO format)
        future_target_time = datetime.now(timezone.utc) + timedelta(
            minutes=delay_minutes
        )
        iso_timestamp_str = future_target_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Step 4: Stitch schema metadata to meet exact specification shapes
        airdrop_payload = {
            "action": "schedule",
            "scheduledAt": iso_timestamp_str,
            "coinTicker": selected_coin["ticker"],
            "coinName": selected_coin["name"],
            "coinLogo": selected_coin.get("logo", "🎯"),
            "coinContractAddress": selected_coin["contract_address"],
        }

        # Step 5: Securely push targeted execution parameters to the protected POST route
        print(
            f"🔒 Authorizing transaction... Scheduling drop for {delay_minutes} min in future."
        )
        try:
            response = client.post(
                AIRDROPS_ENDPOINT, json=airdrop_payload, headers=authenticated_headers
            )

            if response.status_code in [200, 201]:
                print(
                    "\n💾 [SUCCESS] Airdrop timeline synced successfully. Security clearance approved!"
                )
                print(json.dumps(response.json(), indent=2))
            elif response.status_code == 401:
                print(
                    "\n🚨 [AUTH FAILURE] Server rejected credentials. Check your KEEPER_API_KEY match setup."
                )
            else:
                print(
                    f"\n⚠️ [SERVER REJECTION] Status {response.status_code}: {response.text}"
                )

        except Exception as e:
            print(f"❌ Failed to broadcast payload envelope to protected endpoint: {e}")


if __name__ == "__main__":
    # Change this integer value to set your custom countdown test windows (e.g. 5, 10, 180 min)
    TEST_COUNTDOWN_OFFSET_MINUTES = 1

    print("🛠️  Launching Secure Index Scheduler Daemon...")
    schedule_next_roulette_target(delay_minutes=TEST_COUNTDOWN_OFFSET_MINUTES)
