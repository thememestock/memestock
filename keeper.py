import os
import sys
import time
import json
import base64
import random
import httpx
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Solana & Solders Core Connection Modules
from solana.rpc.api import Client
from solana.rpc.types import TxOpts
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.message import to_bytes_versioned

load_dotenv()

# ==============================================================================
# ⚙️ SYSTEM CONFIGURATION REGISTRY
# ==============================================================================
BASE_URL = os.getenv("NEXT_PUBLIC_APP_URL", "https://v0-meme-etf-dashboard.vercel.app")
COINS_ENDPOINT = f"{BASE_URL}/api/coins"
AIRDROPS_ENDPOINT = f"{BASE_URL}/api/airdrops"

SOLANA_RPC_URL = os.getenv("RPC_URL", "https://api.devnet.solana.com")
KEEPER_API_KEY = os.getenv("KEEPER_API_KEY")

if not KEEPER_API_KEY:
    print("❌ CONFIGURATION ERROR: 'KEEPER_API_KEY' must be present in your environment.")
    sys.exit(1)

AUTH_HEADERS = {
    "Authorization": f"Bearer {KEEPER_API_KEY}",
    "Content-Type": "application/json",
}

# Jupiter API Routing Setup
_JUP_API_KEY = os.getenv("JUPITER_API_KEY", "")
_JUP_BASE = "https://api.jup.ag/swap/v1" if _JUP_API_KEY else "https://lite-api.jup.ag/swap/v1"
_JUP_HEADERS = {"x-api-key": _JUP_API_KEY} if _JUP_API_KEY else {}

LAMPORTS_PER_SOL = 1_000_000_000

def fetch_wallet_on_chain_token_balance(rpc_client: Client, sender_pubkey: Pubkey, mint_pubkey: Pubkey) -> float:
    """Queries live on-chain ledger state to extract exact base token asset balances."""
    try:
        # Re-creating the derived ATA using standard Solana layout seeds matching system specs
        # spl-token program id: TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA
        token_program_id = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
        
        # Derive associated token account address manually
        ata_pubkey, _ = Pubkey.find_program_address(
            [bytes(sender_pubkey), bytes(token_program_id), bytes(mint_pubkey)],
            Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
        )

        balance_res = rpc_client.get_token_account_balance(ata_pubkey)
        if balance_res.value is None:
            return 0.0
        return float(balance_res.value.ui_amount)
    except Exception:
        return 0.0


def run_autonomous_scheduler(solana_client: Client):
    print("Evaluating database queue... Running Provably Fair Scheduler...")
    try:
        # Pull current node epoch position 
        slot = solana_client.get_slot().value
        block_res = solana_client.get_block(slot, max_supported_transaction_version=0)
        if not block_res or not block_res.value:
            print("   ⚠️ Failed to grab recent block hash. Skipping schedule tick.")
            return
        
        block_hash = str(block_res.value.blockhash)
        print(f"   🔗 Retreived Block #{slot} Hash: {block_hash}")
        
        with httpx.Client(timeout=10.0) as client:
            coins_res = client.get(COINS_ENDPOINT)
            if coins_res.status_code != 200:
                print(f"   ⚠️ Could not reach token pool API [HTTP {coins_res.status_code}].")
                return
            coin_pool = coins_res.json().get("data", [])
            
        if len(coin_pool) < 3:
            print("   ⚠️ Database asset registry contains less than 3 tokens. Cannot schedule.")
            return

        # Seed randomizer deterministically using the live block hash
        random.seed(block_hash)
        selected_coins = random.sample(coin_pool, 3)
        
        print(f"   🎯 Selected: {', '.join([c['ticker'] for c in selected_coins])}. Pushing schedules...")
        
        with httpx.Client(timeout=15.0) as client:
            for i, coin in enumerate(selected_coins):
                offset_minutes = 10 + (i * 10)  # Distribute in clean 10-minute waves
                future_time = datetime.now(timezone.utc) + timedelta(minutes=offset_minutes)
                
                payload = {
                    "action": "schedule",
                    "scheduledAt": future_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "coinTicker": coin["ticker"],
                    "coinName": coin["name"],
                    "coinLogo": coin.get("logo", "🎯"),
                    "coinContractAddress": coin["contract_address"],
                    "blockNumber": slot,
                    "blockHash": block_hash,
                }
                res = client.post(AIRDROPS_ENDPOINT, json=payload, headers=AUTH_HEADERS)
                if res.status_code in [200, 201]:
                    print(f"      ✅ Scheduled ${coin['ticker']} for {future_time.strftime('%H:%M:%S')} UTC")
                else:
                    print(f"      ❌ Rejected ${coin['ticker']}: {res.text[:150]}")
                    
        print("✅ Scheduler run finalized.")
    except Exception as e:
        print(f"⚠️ Scheduler Execution Skipped: {e}")

# ==============================================================================
# ⚡ ENGINE 2: JUPITER AUTO-SWAP INFRASTRUCTURE
# ==============================================================================
def execute_jupiter_swap(solana_client: Client, signer_keypair: Keypair, output_mint: str, sol_amount: float) -> str | None:
    """Fetches a quote and performs an on-chain market purchase via Jupiter."""
    input_mint = "So11111111111111111111111111111111111111112"  # Wrapped SOL
    lamports = int(sol_amount * LAMPORTS_PER_SOL)
    
    params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": lamports,
        "slippageBps": 150,  # 1.5% Slippage tolerance for volatile tokens
    }
    
    try:
        with httpx.Client(timeout=10.0) as client:
            quote_res = client.get(f"{_JUP_BASE}/quote", params=params, headers=_JUP_HEADERS)
            if quote_res.status_code != 200:
                print(f"      ❌ Jupiter quote failure [{quote_res.status_code}]")
                return None
            quote_payload = quote_res.json()

        swap_payload = {
            "quoteResponse": quote_payload,
            "userPublicKey": str(signer_keypair.pubkey()),
            "wrapAndUnwrapSol": True,
            "dynamicComputeUnitLimit": True,
            "prioritizationFeeLamports": 60000,
        }

        with httpx.Client(timeout=20.0) as client:
            swap_res = client.post(f"{_JUP_BASE}/swap", json=swap_payload, headers=_JUP_HEADERS)
            if swap_res.status_code != 200:
                print(f"      ❌ Jupiter transaction creation failure [{swap_res.status_code}]")
                return None
            
            base64_tx_str = swap_res.json().get("swapTransaction")
            if not base64_tx_str:
                return None
            
        raw_tx_bytes = base64.b64decode(base64_tx_str)
        tx = VersionedTransaction.from_bytes(raw_tx_bytes)
        sig = signer_keypair.sign_message(to_bytes_versioned(tx.message))
        signed_tx = VersionedTransaction.populate(tx.message, [sig])
        
        tx_res = solana_client.send_raw_transaction(bytes(signed_tx), opts=TxOpts(skip_preflight=False, max_retries=3))
        return str(tx_res.value) if tx_res.value else None
    except Exception as e:
        print(f"   ❌ Jupiter Execution Runtime Fault: {e}")
        return None

# THE FOREVER KEEPER
def run_keeper_daemon():
    solana_client = Client(SOLANA_RPC_URL)
    
    # Extract authorization private key variables safely
    pk_bytes = json.loads(os.getenv("BOT_PRIVATE_KEY", "[]"))
    if not pk_bytes:
        print("❌ CRITICAL: 'BOT_PRIVATE_KEY' environmental array format missing in .env.")
        sys.exit(1)
    sender_keypair = Keypair.from_bytes(pk_bytes)

    print("\n" + "=" * 80)
    print("🤖 AUTO-SCHEDULER & AUTO-SWAPPER BACKGROUND KEEPER DAEMON ONLINE")
    print(f"⚙️  Wallet Authority: {sender_keypair.pubkey()}")
    print(f"🔗 Network RPC Gateway: {SOLANA_RPC_URL}")
    print("=" * 80)

    # Track tokens we've already successfully auto-swapped this wave to prevent loop hammering
    funded_mints = set()

    while True:
        try:
            # 📡 1. Poll Web Infrastructure Queue Status
            with httpx.Client(timeout=10.0) as client:
                res = client.get(AIRDROPS_ENDPOINT)
                if res.status_code != 200:
                    print(f"⚠️ API Poller dropped connection [HTTP {res.status_code}]. Retrying in 10s...")
                    time.sleep(10)
                    continue
                payload = res.json()

            upcoming_queue = payload.get("upcomingAirdrops", [])
            if not upcoming_queue and payload.get("nextAirdrop"):
                upcoming_queue = [payload["nextAirdrop"]]

            # 🛠️ 2. Auto-Scheduler Trigger
            if not upcoming_queue:
                print("📭 Web queue contains 0 items. Triggering automated seed allocation sequence...")
                run_autonomous_scheduler(solana_client)
                funded_mints.clear()  # Reset funding trackers for the new batch
                time.sleep(10)
                continue

            # Look at the priority item at the top of the queue stack
            airdrop = upcoming_queue[0]
            airdrop_id = airdrop["id"]
            coin_metadata = airdrop.get("coin", {})
            
            target_mint_address = coin_metadata.get("contractAddress") or coin_metadata.get("contract_address")
            ticker = coin_metadata.get("ticker", "UNKNOWN")
            time_remaining_seconds = int(airdrop.get("timeRemaining", 0)) / 1000.0

            if not target_mint_address:
                time.sleep(5)
                continue

            # 💰 3. Auto-Swap Trigger Evaluation Loop
            # Only trigger swap funding checks if the wave has more than 10 seconds left (giving time for transaction blocks)
            if time_remaining_seconds > 10 and target_mint_address not in funded_mints:
                mint_pubkey = Pubkey.from_string(target_mint_address)
                
                # Fetch on-chain balance
                ui_balance = fetch_wallet_on_chain_token_balance(solana_client, sender_keypair.pubkey(), mint_pubkey)
                
                # If balance is critically low, hit Jupiter swap pipeline immediately
                if ui_balance <= 10:
                    AUTO_SWAP_SOL_AMOUNT = 0.25  # Amount of SOL to spend to secure token pool injection
                    print(f"🛒 Low Balance Warning: Wallet holds {ui_balance:.2f} ${ticker}. Executing Market Buy via Jupiter...")
                    
                    tx_sig = execute_jupiter_swap(solana_client, sender_keypair, target_mint_address, AUTO_SWAP_SOL_AMOUNT)
                    if tx_sig:
                        print(f"   ✅ Auto-Swap Complete! Tokens Secured. Tx Signature: {tx_sig[:16]}...")
                        funded_mints.add(target_mint_address)
                    else:
                        print("   ❌ Auto-Swap failed. Will check again next tick.")
                else:
                    # Account has tokens already, tag as funded so we stop running balance checks for this item
                    funded_mints.add(target_mint_address)

            # ⏳ Standby heartbeat output to terminal
            print(f"💤 [{datetime.now().strftime('%H:%M:%S')}] Monitoring Queue: [Wave #{airdrop.get('airdropNumber')} - ${ticker}] | Remainder: {time_remaining_seconds:.1f}s | Swapped Status: {'✅ Funded' if target_mint_address in funded_mints else '🔍 Pending'}")
            
            if time_remaining_seconds > 30:
                time.sleep(15)
            elif time_remaining_seconds > 0:
                time.sleep(5)
            else:
                # If time_remaining is negative, the external dispatcher script is currently cleaning it out. 
                # Wait a bit, clear out cache trackers, and let the loop cycle.
                funded_mints.discard(target_mint_address)
                time.sleep(10)

        except Exception as e:
            print(f"💥 Master Execution Loop Exception: {e}")
            time.sleep(10)

if __name__ == "__main__":
    run_keeper_daemon()