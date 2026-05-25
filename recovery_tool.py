import os
import json
import glob
from airdrop import AIRDROP, logger


def RECOVER_FAILED_BATCHES(
    TOKEN_MINT: str,
    token_decimals: int = 6,
    coin_ticker: str = "UNKNOWN",
    coin_price_usd: float = 0.0,
):
    """Scans for failed batches, passes data directly into the core AIRDROP engine."""
    failed_files = glob.glob("failed_batches/*.json")
    if not failed_files:
        logger.info("🎉 No failed batches found! You are all caught up.")
        return

    logger.info(
        f"🚨 Found {len(failed_files)} failed batch files. Routing to core engine..."
    )
    os.makedirs("recovered_batches", exist_ok=True)

    for file_path in failed_files:
        filename = os.path.basename(file_path)
        logger.info(f"🔄 Processing recovery file: {filename}")

        try:
            with open(file_path, "r") as f:
                dump_data = json.load(f)
        except Exception as e:
            logger.error(f"Could not read {file_path}: {e}")
            continue

        batch_items = dump_data.get("pending_allocations", [])
        if not batch_items:
            logger.warning(
                f"File {filename} contained no pending allocations. Skipping."
            )
            continue

        # Hand off execution completely to the tested engine wheel
    # Hand off execution completely to the tested engine wheel
        success = AIRDROP(
            holder_percentages={},
            TOKEN_MINT=TOKEN_MINT,
            token_decimals=token_decimals,
            coin_ticker=coin_ticker,
            coin_price_usd=coin_price_usd,
            precalculated_allocations=batch_items,
        )
        if success:
            os.rename(file_path, f"recovered_batches/{filename}")
            logger.info(f"✅ Successfully recovered and archived: {filename}")
        else:
            logger.error(
                f"❌ Recovery failed again for {filename}. Left in processing queue."
            )


if __name__ == "__main__":
    MY_MINT = "7SSNYfoHo2ujFWaGkxMhgne7ZtAMsJwhhYMD2p3hx8fp"

    RECOVER_FAILED_BATCHES(
        TOKEN_MINT=MY_MINT,
        token_decimals=6,
        coin_ticker="TripleT",
        coin_price_usd=0.275,
    )
