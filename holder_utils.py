import os
import json
import struct
import base64
import hashlib
import logging
import base58
import httpx
from bisect import bisect_right
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Set, Optional
from collections import defaultdict
import time
from dataclasses import dataclass
from dotenv import load_dotenv

# --- LOAD ENVIRONMENT ---
load_dotenv()

# --- PROJECT CONSTANTS ---
TOKEN_MINT = "bkJaJVZbry13acp171VApiM7oh29uUFueuurSTrmeme"
TOKEN_DECIMALS = 6

# 1,000,000 tokens (which is exactly 0.1% of a 1 Billion supply)
MIN_RAW_BALANCE = 1_000_000 * (10**TOKEN_DECIMALS)

TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM_ID = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
EXCLUDED_WALLETS_FILE = "excluded_wallets.mainnet.txt"


@dataclass(frozen=True)
class HolderRange:
    address: str
    balance: int
    start_ticket: int
    end_ticket: int


# --- CORE UTILITIES ---


class RpcClient:
    def __init__(self, rpc_url: str, timeout_s: float = 60.0):
        self.rpc_url = rpc_url
        self.client = httpx.Client(timeout=timeout_s)

    def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = self.client.post(self.rpc_url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"RPC error: {data['error']}")
        return data

    def get_blockhash_for_slot(
        self, slot: int, max_retries: int = 20, delay: float = 3.0
    ) -> str:
        current_slot = int(slot)

        for attempt in range(max_retries):
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getBlock",
                "params": [
                    current_slot,
                    {
                        "encoding": "json",
                        "transactionDetails": "none",
                        "rewards": False,
                        "commitment": "finalized",  # Ensures we only get immutable blocks
                    },
                ],
            }

            try:
                data = self._post(payload)
                result = data.get("result")
                if result and "blockhash" in result:
                    return result["blockhash"]
            except RuntimeError as e:
                error_msg = str(e)

                # -32004: Block not available yet (still processing/finalizing)
                if "-32004" in error_msg or "Block not available" in error_msg:
                    print(
                        f"   ⏳ [RPC] Block {current_slot} not finalized yet. Waiting {delay}s... ({attempt + 1}/{max_retries})"
                    )
                    time.sleep(delay)

                # -32007 or -32009: Slot was skipped by the network
                elif (
                    "-32007" in error_msg
                    or "-32009" in error_msg
                    or "skipped" in error_msg.lower()
                ):
                    print(
                        f"   ⏭️ [RPC] Slot {current_slot} was SKIPPED by network. Checking next slot: {current_slot + 1}..."
                    )
                    current_slot += 1
                    time.sleep(1)

                # Unknown error
                else:
                    raise e

        raise RuntimeError(f"Timeout waiting for block {slot} to become finalized.")

    def get_program_accounts_base64(
        self, program_id: str, mint: str, classic: bool
    ) -> List[str]:
        filters: List[Dict[str, Any]] = [{"memcmp": {"offset": 0, "bytes": mint}}]
        if classic:
            filters.append({"dataSize": 165})

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getProgramAccounts",
            "params": [program_id, {"encoding": "base64", "filters": filters}],
        }
        data = self._post(payload)
        return [item["account"]["data"][0] for item in data.get("result", [])]

    def close(self):
        self.client.close()


def parse_owner_and_amount(data: bytes) -> Optional[Tuple[str, int]]:
    if len(data) < 72:
        return None
    owner = base58.b58encode(data[32:64]).decode("ascii")
    amount = struct.unpack("<Q", data[64:72])[0]
    return owner, amount


def load_excluded_wallets() -> Set[str]:
    out = set()
    if not os.path.exists(EXCLUDED_WALLETS_FILE):
        return out
    with open(EXCLUDED_WALLETS_FILE, "r") as f:
        for line in f:
            w = line.strip()
            if w and not w.startswith("#"):
                out.add(w)
    return out


# --- LOTTERY MATH ---


def build_ranges(eligible: List[Tuple[str, int]]) -> Tuple[List[HolderRange], int]:
    ranges = []
    cursor = 0
    for addr, bal in eligible:
        start, end = cursor, cursor + bal
        ranges.append(HolderRange(addr, bal, start, end))
        cursor = end
    return ranges, cursor


def compute_ticket(seed: str, total_tickets: int) -> Tuple[int, str, int]:
    seed_hash_hex = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    seed_int = int(seed_hash_hex, 16)
    return seed_int % total_tickets, seed_hash_hex, seed_int


def find_winner(ranges: List[HolderRange], ticket: int) -> HolderRange:
    ends = [r.end_ticket for r in ranges]
    idx = bisect_right(ends, ticket)
    return ranges[idx]


# --- MAIN DRAW FUNCTION ---


def draw(slot: int) -> Tuple[str, str]:
    """
    Performs a verifiable draw for a specific Solana slot.
    Returns: (winner_address, block_hash)
    """
    rpc_url = os.getenv("RPC_URL")
    if not rpc_url:
        raise ValueError("RPC_URL not found in .env")

    rpc = RpcClient(rpc_url)
    try:
        # 1. Fetch the seed (blockhash)
        target_slot = int(slot)
        print(f"🧬 Fetching seed for slot {target_slot}...")
        seed = rpc.get_blockhash_for_slot(target_slot)

        # 2. Fetch all token accounts
        print(f"🛰️  Scanning token holders for mint {TOKEN_MINT}...")
        all_b64 = rpc.get_program_accounts_base64(
            TOKEN_PROGRAM_ID, TOKEN_MINT, True
        ) + rpc.get_program_accounts_base64(TOKEN_2022_PROGRAM_ID, TOKEN_MINT, False)

        # 3. Aggregate and Filter
        balances = defaultdict(int)
        for b64 in all_b64:
            parsed = parse_owner_and_amount(base64.b64decode(b64))
            if parsed:
                owner, amount = parsed
                if amount > 0:
                    balances[owner] += int(amount)

        excluded = load_excluded_wallets()
        eligible = [
            (addr, bal)
            for addr, bal in balances.items()
            if addr not in excluded and bal >= MIN_RAW_BALANCE
        ]
        eligible.sort(key=lambda x: x[0])  # Critical for determinism

        # 4. Build ranges and pick winner
        ranges, total_tickets = build_ranges(eligible)
        if total_tickets <= 0:
            raise RuntimeError("No eligible entrants found.")

        ticket, seed_hash_hex, seed_int = compute_ticket(seed, total_tickets)
        winner = find_winner(ranges, ticket)

        # 5. Generate Audit File
        audit_filename = f"{target_slot}_draw.json"
        audit_data = {
            "metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "token_mint": TOKEN_MINT,
                "target_slot": target_slot,
                "seed_blockhash": seed,
                "seed_hash_hex": seed_hash_hex,
                "total_tickets": total_tickets,
                "winning_ticket": ticket,
            },
            "winner": {"address": winner.address, "balance": winner.balance},
            "all_entrants": [
                {
                    "address": r.address,
                    "balance": r.balance,
                    "start": r.start_ticket,
                    "end": r.end_ticket,
                }
                for r in ranges
            ],
        }

        with open(audit_filename, "w") as f:
            json.dump(audit_data, f, indent=2)

        print(f"✅ Draw Successful! Audit saved to {audit_filename}")
        return winner.address, seed

    finally:
        rpc.close()


def get_holder_percentages() -> List[Dict[str, Any]]:
    """
    Fetches all token holders, filters out excluded wallets, and
    calculates the exact ownership percentage of each remaining holder.
    """
    rpc_url = os.getenv("RPC_URL")
    if not rpc_url:
        raise ValueError("RPC_URL not found in .env")

    rpc = RpcClient(rpc_url)
    try:
        print(f"🛰️  Scanning token holders for mint {TOKEN_MINT}...")
        # 1. Fetch data from both Token Programs
        all_b64 = rpc.get_program_accounts_base64(
            TOKEN_PROGRAM_ID, TOKEN_MINT, True
        ) + rpc.get_program_accounts_base64(TOKEN_2022_PROGRAM_ID, TOKEN_MINT, False)

        # 2. Aggregate raw token balances per wallet address
        balances = defaultdict(int)
        for b64 in all_b64:
            parsed = parse_owner_and_amount(base64.b64decode(b64))
            if parsed:
                owner, amount = parsed
                if amount > 0:
                    balances[owner] += int(amount)

        # 3. Load exclusions and build the eligible pool
        excluded = load_excluded_wallets()

        # Filter out excluded wallets and those below the minimum required balance
        eligible_holders = {
            addr: bal
            for addr, bal in balances.items()
            if addr not in excluded and bal >= MIN_RAW_BALANCE
        }

        # 4. Calculate the adjusted total supply of the eligible pool
        total_eligible_supply = sum(eligible_holders.values())

        if total_eligible_supply == 0:
            print("⚠️ No eligible holders found matching the criteria.")
            return []

        # 5. Compute the final human-readable balances and percentages
        holder_distribution = []
        for addr, bal in eligible_holders.items():
            # Convert raw structural units (lamports-equivalent for tokens) using your token decimals
            human_balance = bal / (10**TOKEN_DECIMALS)
            percentage = bal / total_eligible_supply

            holder_distribution.append(
                {
                    "address": addr,
                    "raw_balance": bal,
                    "balance": human_balance,
                    "percentage": round(percentage, 4),
                }
            )

        # Sort from largest holder to smallest holder
        holder_distribution.sort(key=lambda x: x["percentage"], reverse=True)

        return holder_distribution

    finally:
        rpc.close()
