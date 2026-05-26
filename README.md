---
# 🤖 Solana MemeStock ETF Keeper Engine

[![Solana Mainnet](https://img.shields.io/badge/Solana-Mainnet--Beta-blueviolet?logo=solana)](https://solana.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

*“A meme stock is a company whose valuation surges rapidly due to online hype rather than business fundamentals. No one knows what the next token dividend will be; only the chain does. Will it make the right decisions?”*

This repository houses the autonomous orchestration backend for the **$MEME Total Market Index**. It operates as a high-frequency, automated keeper daemon on the Solana network that processes taxes, swaps revenues via the Jupiter Aggregator, and executes pro-rata atomic batch airdrops to qualified holders based on fully verifiable, on-chain randomness.

---

## 🏛️ The Protocol: Code Meets Concept

This backend explicitly executes the three pillars of the protocol announced in our official documentation:

### 1️⃣ The Concept: 5% Revenue Flywheel
Post-bonding curve completion, a **5% tax** is imposed on transactions. These fees accumulate as wrapped SOL (wSOL) inside our Meteora liquidity position. The Keeper Daemon continuously monitors this position and uses the accumulated wSOL to purchase X amount of a randomly chosen token for the upcoming distribution event.

### 2️⃣ Provable Randomness: The Chain Decides
To ensure the protocol is completely impossible to manipulate or front-run, randomness is anchored entirely to the Solana ledger:
* Distributions are computed in automated **bundles of 3 tokens**.
* The winning trio of memecoins is determined via a single *future* Solana slot block hash, announced publicly before the block is validated.
* Because no one has access to a future block hash, it is impossible to predict. Once validated, our `keeper.py` script uses that block hash as the deterministic random seed (`random.seed(block_hash)`) to select the tokens from our Top 50 index. 
* This process is entirely independently verifiable by cross-referencing the slot hash with this open-source algorithm.

### 3️⃣ Transparency: The Dashboard
Human intervention is completely bypassed. Every cycle and every token purchased is directly reflected on our dashboard. The engine syncs real-time execution logs directly to the public web ledger, allowing users to look up total dividends for a single wallet address.

---

## 📊 Tokenomics & Eligibility

To ensure full structural transparency, the protocol adheres to strict mechanical rules:

* **The Index Basket:** The index tracks the top 50 memecoins on Solana sorted by circulating market capitalization (e.g., $WIF, $BONK, $PENGU). The contract addresses are managed via our pre-curated token registry.
* **Holder Eligibility:** To mitigate  manipulation, all holders get airdropped a proportionate supply of the winning token relative to their holdings, provided they hold a minimum balance of **100,000 $MEME**.
* **Exclusions:** Core developer allocations, marketing vaults, liquidity pools, and centralized exchanges are filtered out permanently via `excluded_wallets.mainnet.txt` to keep payouts focused purely on organic ecosystem holders.

---

## 📁 Repository Structure

```text
├── keeper.py          # Unified background daemon (Auto-Scheduler + Jupiter Auto-Swapper)
├── dispatcher.py      # Core orchestration loop & cron-like dispatch tracking engine
├── airdrop.py         # SPL program layouts & packed atomic multi-drops logic
├── holder_utils.py    # Snapshot engine compiling proportional holding weights
├── coin_upload.py     # Hardcoded asset matrix initializing the Top 50 index registry
└── README.md          # Project documentation

```

---

## 🚀 Quick Start & Deployment

### 1. Prerequisites

Ensure you have Python 3.10+ installed along with standard native cryptographic bindings.

```bash
python --version

```

### 2. Installation

Clone the repository and install the required asynchronous networking and Web3 dependencies:

```bash
git clone [https://github.com/your-username/memecoin-etf-keeper.git](https://github.com/your-username/memecoin-etf-keeper.git)
cd memecoin-etf-keeper
pip install -r requirements.txt

```

### 3. Environment Configuration

Create a `.env` file in the root directory using the layout parameters below:

```ini
# RPC Node Gateway Configuration (Use high-performance private endpoints for Mainnet)
RPC_URL="[https://api.mainnet-beta.solana.com](https://api.mainnet-beta.solana.com)"

# Web Dashboard Sync Credentials
NEXT_PUBLIC_APP_URL="[https://your-dashboard-deployment.vercel.app](https://your-dashboard-deployment.vercel.app)"
KEEPER_API_KEY="your-highly-secure-backend-rest-token"

# Automated Executor Wallet Secure Signer (JSON Byte Array Format)
BOT_PRIVATE_KEY="[12, 234, 54, 11, ... 89, 74]"

# Jupiter API (Optional Paid Tier Key)
JUPITER_API_KEY="your-jupiter-portal-key"

```

### 4. Running the Keeper Daemon

Run the persistent daemon loop to listen for state changes, swap liquidity, and execute distribution waves autonomously:

```bash
python keeper.py

```

---

## 🛡️ Security Considerations

> **Warning: Private Key Handling**
> The `BOT_PRIVATE_KEY` variable grants complete programmatic signing authority over the fee-collecting operator wallet.
> * **Never** commit the `.env` file to version control systems.
> * **Never** expose raw private keys inside production logs or telemetry traces.
> * Ensure your server environment is properly secured and isolated.
> 
> 

```
