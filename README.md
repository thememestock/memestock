# 🤖 Memecoin ETF Automation Keeper Engine

The autonomous orchestration backend for the **$Memecoin Total Market Index**.

This system operates as an automated keeper daemon on the Solana network. It monitors the dashboard queue, claims accumulated wSOL trading fees from Meteora Dynamic AMMs, swaps them for a randomly selected index asset via the Jupiter Aggregator, and executes pro-rata atomic batch airdrops to qualified holders using an immutable on-chain blockhash as a randomness seed.

---

## ⚙️ How the Mechanism Works

```
[ Meteora LP 5% Fees ] ──> ( Accrues wSOL ) ──> [ Keeper Daemon Triggers ]
                                                           │
 [ Pro-Rata Multi-Drop ] <── [ Jupiter Swap Target ] <─────┘ ( Seeded by Blockhash )

```

1. **Fee Accumulation:** Every trade on the Meteora $Memecoin pool charges a 5% Liquidity Provider fee. These fees accumulate as wrapped SOL (`wSOL`) inside the LP position held by the operator.
2. **Provably Fair Selection:** Before each distribution cycle, a future Solana block number is locked in. When that block is mined, its unpredictable blockhash seeds the selection algorithm to pick one of the 50 supported basket assets (e.g., `$PENGU`, `$WIF`, `$BONK`).
3. **Liquidity Routing:** Upon countdown expiration, the keeper claims the accrued `wSOL` fees, handles gas reserves, and swaps 100% of the active balance into the chosen target coin using Jupiter.
4. **Packed Atomic Distributions:** The engine pulls an on-chain snapshot of $Memecoin balances via `holder_utils`. Wallets holding $\ge$ 100,000 $Memecoin receive their exact percentage share of the acquired token via packed batch transactions.
5. **State Synchronization:** The execution metrics (USD Value, SOL spent, recipients count) are committed to the web app dashboard via an authenticated REST ledger sync.

---

## 📁 Repository Structure

```text
├── keeper.py          # Core orchestration loop & cron-like dispatch daemon
├── airdrop.py         # Modular Engine Core (SPL program layouts, packed multi-drops)
├── holder_utils.py    # Snapshot engine compiling proportional holding weights
├── .env.example       # System configuration environmental baseline template
└── README.md          # Project documentation

```

---

## 🚀 Quick Start & Deployment

### 1. Prerequisites

Ensure you have Python 3.10+ installed along with standard cryptographic bindings.

```bash
python --version

```

### 2. Installation

Clone the repository and install the required dependencies:

```bash
git clone https://github.com/your-username/memecoin-etf-keeper.git
cd memecoin-etf-keeper
pip install -r requirements.txt

```

> **Note:** Required dependencies include `solana`, `solders`, `httpx`, and `python-dotenv`.

### 3. Environment Configuration

Create a `.env` file in the root directory using the layout parameters below:

```env
# RPC Node Gateway Configuration
RPC_URL="https://api.mainnet-beta.solana.com"

# Web Dashboard Sync Credentials
NEXT_PUBLIC_APP_URL="https://your-dashboard-deployment.vercel.app"
KEEPER_API_KEY="your-highly-secure-backend-rest-token"

# Automated Executor Wallet Secure Signer (JSON Byte Array Format)
BOT_PRIVATE_KEY="[12, 234, 54, 11, ... 89, 74]"

```

### 4. Running the Keeper Daemon

Run the script to spin up the persistent poller interface:

```bash
python keeper.py

```

---

## 📡 API Core Mappings & Fallbacks

* **Market Pricing Reference:** Fetches live index values via CoinGecko API with a built-in fallback baseline threshold of `$85.00` per SOL if rate limits are hit.
* **On-Chain Asset Valuations:** Dynamically queries live liquid asset pricing vectors via the DexScreener Token API (`[https://api.dexscreener.com/latest/dex/tokens/](https://api.dexscreener.com/latest/dex/tokens/)`).
* **Wallet Balance Safety Gate:** The executor enforces a balance check. If the local vault contains less than 10 units of the selected index token asset, the distribution cycle aborts execution to prevent empty transactions.

---

## 🛡️ Security Considerations

> [!WARNING]
> **Private Key Handling:** The `BOT_PRIVATE_KEY` variable gives complete programmatic signing control over the fee-collecting operator wallet. Ensure it is never committed to version control systems or exposed inside production log traces. Always use local system environment constraints or key vaults.

---
