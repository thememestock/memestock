import os
import sys
import json
import logging
import time
import random
from typing import Dict, List
from dotenv import load_dotenv
import httpx

from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solana.rpc.api import Client
from solders.compute_budget import set_compute_unit_price, set_compute_unit_limit
from solders.transaction import VersionedTransaction
from solders.message import MessageV0
from solders.instruction import Instruction, AccountMeta
from solana.rpc.types import TxOpts

from spl.token.constants import (
    TOKEN_PROGRAM_ID,
    TOKEN_2022_PROGRAM_ID,
    ASSOCIATED_TOKEN_PROGRAM_ID,
)
from spl.token.instructions import transfer_checked, TransferCheckedParams

load_dotenv()

# ==============================================================================
# 📝 LOGGING SYSTEM CONFIGURATION
# ==============================================================================
logger = logging.getLogger("AirdropEngine")
logger.setLevel(logging.INFO)

log_formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)

file_handler = logging.FileHandler("airdrop_system.log")
file_handler.setFormatter(log_formatter)

error_handler = logging.FileHandler("airdrop_errors.log")
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(log_formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)
logger.addHandler(error_handler)

DEVNET_RPC = "https://api.devnet.solana.com"
RPC_URL = os.getenv("RPC_URL")


# ==============================================================================
# 🚨 EMERGENCY DUMP SYSTEM
# ==============================================================================
def dump_failed_batch(batch_items: List[Dict], reason: str):
    """Saves unconfirmed/failed batches to disk for easy retry."""
    if not batch_items:
        return

    try:
        os.makedirs("failed_batches", exist_ok=True)
        filename = f"failed_batches/emergency_dump_{int(time.time())}.json"

        dump_data = {
            "timestamp": time.time(),
            "reason": reason,
            "items_count": len(batch_items),
            "pending_allocations": batch_items,
        }

        with open(filename, "w") as f:
            json.dump(dump_data, f, indent=4)
        logger.error(f"🚨 EMERGENCY DUMP SAVED: {filename} - {reason}")
    except Exception as e:
        logger.critical(
            f"CRITICAL: Failed to dump batch! Data: {batch_items} Error: {e}"
        )


# ==============================================================================
# ⚡ HELIUS CU OPTIMIZATION
# ==============================================================================
def get_helius_priority_fee(rpc_url: str) -> int:
    """Fetches dynamic recommended priority fee from Helius once per cycle."""
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "getPriorityFeeEstimate",
            "params": [
                {
                    "options": {
                        # Explicitly demand high percentile to reliably cut through congestion
                        "priorityLevel": "High"
                    }
                }
            ],
        }
        with httpx.Client(timeout=5.0) as client:
            res = client.post(rpc_url, json=payload)
            data = res.json()
            if "result" in data and "priorityFeeEstimate" in data["result"]:
                fee = int(data["result"]["priorityFeeEstimate"])
                return max(fee, 10_000)
    except Exception as e:
        logger.warning(f"Failed to fetch Helius priority fee, falling back to 25k: {e}")

    return 25_000


# ==============================================================================
# 🛠️ SOLANA UTILS
# ==============================================================================
def get_associated_token_address_with_program_id(
    wallet_address: Pubkey,
    mint_address: Pubkey,
    token_program_id: Pubkey,
) -> Pubkey:
    return Pubkey.find_program_address(
        [bytes(wallet_address), bytes(token_program_id), bytes(mint_address)],
        ASSOCIATED_TOKEN_PROGRAM_ID,
    )[0]


def sync_batch_to_api(
    batch_items: List[Dict], tx_signature: str, ticker: str, price_usd: float
):
    api_key = os.getenv("KEEPER_API_KEY")
    base_url = os.getenv("NEXT_PUBLIC_APP_URL")

    if not api_key or not base_url:
        logger.warning(
            "Skipping API Sync: 'KEEPER_API_KEY' or 'NEXT_PUBLIC_APP_URL' not found."
        )
        return

    endpoint = f"{base_url}/api/distributions"
    distributions_list = []

    for item in batch_items:
        amount = item["cut"]
        usd_value = round(amount * price_usd, 2)
        distributions_list.append(
            {
                "address": item["wallet"],
                "totalValueUSD": usd_value,
                "tokens": [
                    {
                        "ticker": ticker,
                        "amount": amount,
                        "valueUSD": usd_value,
                        "txSignature": tx_signature,
                    }
                ],
            }
        )

    payload = {"action": "sync", "distributions": distributions_list}

    try:
        with httpx.Client(timeout=15.0) as client:
            res = client.post(
                endpoint, json=payload, headers={"Authorization": f"Bearer {api_key}"}
            )
            if res.status_code in [200, 201]:
                logger.info(f"✅ DB Sync Success: {len(batch_items)} profiles updated.")
            else:
                logger.error(f"DB Sync Failed [{res.status_code}]: {res.text}")
    except Exception as e:
        logger.error(f"Network error syncing to API: {e}")


def get_token_program_for_mint(rpc_client: Client, mint_pubkey: Pubkey) -> Pubkey:
    account_info = rpc_client.get_account_info(mint_pubkey)
    if account_info.value is None:
        raise ValueError(f"Target Mint {mint_pubkey} does not exist.")
    return account_info.value.owner


def create_universal_idempotent_ata_instruction(
    funding_address: Pubkey,
    wallet_address: Pubkey,
    mint_address: Pubkey,
    token_program_id: Pubkey,
) -> Instruction:
    ata_address = get_associated_token_address_with_program_id(
        wallet_address, mint_address, token_program_id
    )
    accounts = [
        AccountMeta(pubkey=funding_address, is_signer=True, is_writable=True),
        AccountMeta(pubkey=ata_address, is_signer=False, is_writable=True),
        AccountMeta(pubkey=wallet_address, is_signer=False, is_writable=False),
        AccountMeta(pubkey=mint_address, is_signer=False, is_writable=False),
        AccountMeta(
            pubkey=Pubkey.from_string("11111111111111111111111111111111"),
            is_signer=False,
            is_writable=False,
        ),
        AccountMeta(pubkey=token_program_id, is_signer=False, is_writable=False),
    ]
    return Instruction(
        program_id=ASSOCIATED_TOKEN_PROGRAM_ID, accounts=accounts, data=b"\x01"
    )


def send_transaction_block(
    client: Client,
    signer: Keypair,
    instructions: List[Instruction],
    current_batch: List[Dict],
):
    """Compile, sign, send, wait for confirmation AND verify instruction execution success."""
    try:
        latest = client.get_latest_blockhash(commitment="processed")
        recent_blockhash = latest.value.blockhash

        message = MessageV0.try_compile(
            payer=signer.pubkey(),
            instructions=instructions,
            address_lookup_table_accounts=[],
            recent_blockhash=recent_blockhash,
        )
        tx = VersionedTransaction(message, [signer])

        res = client.send_transaction(
            tx,
            opts=TxOpts(
                skip_preflight=True, preflight_commitment="processed", max_retries=5
            ),
        )
        tx_sig = res.value
        logger.info(f"🚀 Tx Dispatched! Sig: {tx_sig}. Awaiting confirmation...")

        # 1. Wait for the transaction to be included in a block
        confirmation = client.confirm_transaction(tx_sig, commitment="confirmed")

        if not confirmation.value:
            logger.error(f"❌ Tx {tx_sig} dropped or blockhash expired before landing.")
            dump_failed_batch(current_batch, f"Tx dropped/unconfirmed: {tx_sig}")
            return None

        # 2. Verify if the instructions inside the landed transaction actually succeeded
        status_res = client.get_signature_statuses([tx_sig])
        if status_res.value and status_res.value[0]:
            tx_status = status_res.value[0]

            # If 'err' is not None, the transaction failed on-chain (e.g., Insufficient Funds)
            if tx_status.err is not None:
                logger.error(
                    f"❌ Tx {tx_sig} landed but FAILED on-chain. Error details: {tx_status.err}"
                )
                dump_failed_batch(
                    current_batch, f"On-chain execution failure: {tx_status.err}"
                )
                return None

        logger.info(f"✅ Tx {tx_sig} processed and finalized successfully.")
        return str(tx_sig)

    except Exception as e:
        logger.error(f"❌ Execution block failed: {e}")
        dump_failed_batch(current_batch, str(e))
        return None


# ==============================================================================
# 🚀 CORE ENGINE
# ==============================================================================
def AIRDROP(
    holder_percentages: Dict[str, float],
    TOKEN_MINT: str,
    total_tokens_avail: float,
    token_decimals: int = 6,
    coin_ticker: str = "UNKNOWN",
    coin_price_usd: float = 0.0,
    precalculated_allocations: List[Dict] = None,
):
    rpc_client = Client(DEVNET_RPC)
    mint_pubkey = Pubkey.from_string(TOKEN_MINT)

    try:
        target_token_program = get_token_program_for_mint(rpc_client, mint_pubkey)
    except Exception as e:
        logger.error(f"Failed connection lookup parameters: {e}")
        return

    pk_bytes = json.loads(os.getenv("BOT_PRIVATE_KEY", "[]"))
    sender_keypair = Keypair.from_bytes(pk_bytes)
    sender_pubkey = sender_keypair.pubkey()
    sender_ata = get_associated_token_address_with_program_id(
        sender_pubkey, mint_pubkey, target_token_program
    )

    if precalculated_allocations is not None:
        allocations = precalculated_allocations
    else:
        total_entered_weight = sum(holder_percentages.values())
        allocations = []
        for addr, percentage in holder_percentages.items():
            wallet_token_cut = total_tokens_avail * (percentage / total_entered_weight)
            raw_amount = int(wallet_token_cut * (10**token_decimals))
            if raw_amount > 0:
                allocations.append(
                    {"wallet": addr, "raw_amount": raw_amount, "cut": wallet_token_cut}
                )

    # ⚡ OPTIMIZATION: Query dynamic priority fee exactly ONCE per distribution runtime cycle
    global_fee = get_helius_priority_fee(RPC_URL)
    logger.info(f"Using dynamic cycle-level priority fee: {global_fee} micro-lamports.")

    BATCH_SIZE = 8
    current_batch_items = []

    # Strictly bound to ~220,000 based on your real 175,986 CU transaction data
    instructions_stack = [
        set_compute_unit_limit(220_000),
        set_compute_unit_price(global_fee),
    ]

    logger.info("Assembling idempotent distribution batches...")
    for item in allocations:
        receiver_pubkey = Pubkey.from_string(item["wallet"])
        receiver_ata = get_associated_token_address_with_program_id(
            receiver_pubkey, mint_pubkey, target_token_program
        )

        instructions_stack.append(
            create_universal_idempotent_ata_instruction(
                sender_pubkey, receiver_pubkey, mint_pubkey, target_token_program
            )
        )

        instructions_stack.append(
            transfer_checked(
                TransferCheckedParams(
                    program_id=target_token_program,
                    source=sender_ata,
                    mint=mint_pubkey,
                    dest=receiver_ata,
                    owner=sender_pubkey,
                    amount=item["raw_amount"],
                    decimals=token_decimals,
                    signers=[],
                )
            )
        )
        current_batch_items.append(item)

        if (len(instructions_stack) - 2) // 2 >= BATCH_SIZE:
            tx_sig = send_transaction_block(
                rpc_client, sender_keypair, instructions_stack, current_batch_items
            )

            if tx_sig:
                sync_batch_to_api(
                    current_batch_items, tx_sig, coin_ticker, coin_price_usd
                )

            current_batch_items.clear()
            instructions_stack = [
                set_compute_unit_limit(220_000),
                set_compute_unit_price(global_fee),
            ]

    # Clean out tail buffer
    if len(instructions_stack) > 2:
        tx_sig = send_transaction_block(
            rpc_client, sender_keypair, instructions_stack, current_batch_items
        )
        if tx_sig:
            sync_batch_to_api(current_batch_items, tx_sig, coin_ticker, coin_price_usd)

    return True


if __name__ == "__main__":
    MY_DEVNET_TEST_MINT = "Hbk6TXTL2gP8DC9w6HENkd2ukE1kZ44JuUxnsvvi2ynk"
    ACTIVE_TICKER = "GOAT"
    CURRENT_TOKEN_PRICE = 0.275

    logger.info("Programmatically simulating 20 unique community holders...")
    stress_test_snapshot = {
        str(Keypair().pubkey()): round(random.uniform(0.01, 5.00), 4) for _ in range(20)
    }

    TOTAL_TOKENS_AVAILABLE_TO_AIRDROP = 100000.0

    start_time = time.time()
    AIRDROP(
        holder_percentages=stress_test_snapshot,
        TOKEN_MINT=MY_DEVNET_TEST_MINT,
        total_tokens_avail=TOTAL_TOKENS_AVAILABLE_TO_AIRDROP,
        token_decimals=6,
        coin_ticker=ACTIVE_TICKER,
        coin_price_usd=CURRENT_TOKEN_PRICE,
    )

    logger.info(f"Airdrop Run Completed in {(time.time() - start_time):.2f} seconds!")
