import holder_utils
import os

EXCLUDED_WALLETS_FILE = "excluded_wallets.mainnet.txt"

if __name__ == "__main__":
    # Ensure you have an 'excluded_wallets.mainnet.txt' file in the directory
    # Even an empty file works, or put Raydium/Dex pools inside it.
    if not os.path.exists(EXCLUDED_WALLETS_FILE):
        with open(EXCLUDED_WALLETS_FILE, "w") as f:
            f.write("# Add wallet addresses to exclude here (one per line)\n")

    try:
        results = holder_utils.get_holder_percentages()
        print(f"\n📊 Total Eligible Holders: {len(results)}")
        print("-" * 65)
        print(f"{'Wallet Address':<45} | {'Balance':<10} | {'Percentage'}")
        print("-" * 65)

        # Display the top 10 holders as a sample
        for holder in results[:10]:
            print(
                f"{holder['address']:<45} | {holder['balance']:<10,.2f} | {holder['percentage']*100}%"
            )

    except Exception as e:
        print(f"❌ Error compiling distribution: {e}")
