import os
import json
import random
import httpx
from datetime import datetime
from dotenv import load_dotenv
from solders.keypair import Keypair

# Load environment configuration keys
load_dotenv()

# Network Profiles Setup
BASE_URL = os.getenv("NEXT_PUBLIC_APP_URL", "http://localhost:3000")
DISTRIBUTIONS_API_URL = f"{BASE_URL}/api/distributions"


def generate_and_push_bulk_mock_data(wallet_count: int = 10):
    """
    Generates an array of randomized public keys with custom distributed values,
    and executes an authenticated single-trip bulk synchronization to the web server.
    """
    print("\n" + "=" * 80)
    print("🛠️  STARTING VERBOSE AIRDROP DISTRIBUTION SYNC TEST")
    print("=" * 80)

    # 🛡️ 1. Security check
    api_key = os.getenv("KEEPER_API_KEY")
    if not api_key:
        print(
            "❌ ERROR: 'KEEPER_API_KEY' is completely missing from your local .env file."
        )
        return
    else:
        print(
            f"🔒 API Key detected: {api_key[:6]}...{api_key[-4:] if len(api_key) > 4 else ''}"
        )

    auth_headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # 🎲 2. Decide a target coin token to mock out this round
    mock_tickers = ["WIF", "GOAT", "MOG", "POPCAT", "BONK"]
    active_ticker = random.choice(mock_tickers)

    print(f"🧬 Selected Token for this cycle: ${active_ticker}")
    print(f"📦 Staging payload for exactly {wallet_count} mock holders...")
    print("-" * 80)

    distributions_list = []

    # 🔨 3. Generate randomized holder data packets verbose-style
    for i in range(wallet_count):
        # Generate a cryptographically authentic Solana public key
        fake_wallet_address = str(Keypair().pubkey())

        # Throw realistic distribution metrics onto the line
        tokens_received = round(random.uniform(50.0, 15000.0), 4)
        value_usd = round(tokens_received * random.uniform(0.005, 0.05), 2)

        # Generate a fake 88-character Solana base58 transaction signature string
        fake_signature = "MOCK_TX_" + "".join(
            random.choices(
                "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz", k=80
            )
        )

        # Verbose terminal log itemized per wallet entry
        print(f"👤 Wallet #{i+1:02d}: {fake_wallet_address}")
        print(
            f"   └── Allocating: {tokens_received:,.4f} ${active_ticker} (~${value_usd:,.2f} USD)"
        )
        print(f"   └── Tx Sig:     {fake_signature[:16]}...{fake_signature[-12:]}")

        # Structure individual rows matching your exact target schema payload requirements
        distributions_list.append(
            {
                "address": fake_wallet_address,
                "totalValueUSD": value_usd,
                "tokens": [
                    {
                        "ticker": active_ticker,
                        "amount": tokens_received,
                        "valueUSD": value_usd,
                        "txSignature": fake_signature,
                    }
                ],
            }
        )

    print("-" * 80)
    print(
        f"📊 Local staging complete. Total payload batch items ready: {len(distributions_list)}"
    )

    # Wrap inside the mass action sync command envelope
    payload_envelope = {"action": "sync", "distributions": distributions_list}

    # 🚀 4. Fire the complete data matrix down the pipe!
    print(f"📡 Broadcasting to endpoint: {DISTRIBUTIONS_API_URL}...")

    start_time = datetime.now()
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                DISTRIBUTIONS_API_URL, json=payload_envelope, headers=auth_headers
            )

            execution_time = (datetime.now() - start_time).total_seconds()

            if response.status_code in [200, 201]:
                print("\n" + "=" * 80)
                print(
                    f"⚡ [BULK SYNC SUCCESS] Database response status: {response.status_code}"
                )
                print(
                    f"⏱️  Server processing execution speed: {execution_time:.3f} seconds."
                )
                print("=" * 80)
                print("📝 Server Response Envelope JSON:")
                print(json.dumps(response.json(), indent=2))
                print("-" * 80)

                # 📋 Output the full terminal list of generated test wallets for quick copy-pasting
                print("\n🔬 [FE TABLE LOG / COPIABLE WALLETS LIST]")
                print(
                    "Copy ANY of these wallet keys into your Address Tracker UI search engine:"
                )
                print("-" * 80)
                for idx, dist in enumerate(distributions_list):
                    print(
                        f"👉 Wallet {idx+1:02d}: \033[96m{dist['address']}\033[0m  | Value: ${dist['totalValueUSD']:,.2f}"
                    )
                print("-" * 80)

            elif response.status_code == 401:
                print(
                    f"\n🚨 [AUTH REJECTED - 401] Server dropped request. Verify your KEEPER_API_KEY matches exactly."
                )
            else:
                print(
                    f"\n⚠️ [SERVER DROPPED PAYLOAD - {response.status_code}]: {response.text}"
                )

    except Exception as network_err:
        print(f"❌ Failed to push data payload across the network loop: {network_err}")


if __name__ == "__main__":
    # Forced override to exactly 10 profiles for clean terminal reading
    generate_and_push_bulk_mock_data(wallet_count=10)
