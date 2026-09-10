# CryptoIntel — Global Real-Time Crypto Intelligence Platform

This project is **NOT an OSINT framework**. It is a crypto intelligence platform focused on live market data, blockchain activity, wallet/fund-flow investigation, anomaly detection and alerts.

## Core requirements
1. Live crypto prices, trades, volume and order books.
2. Blockchain transactions, wallets and token transfers.
3. Wallet-to-wallet and wallet-to-exchange fund-flow analysis.
4. Suspicious-activity indicators and anomaly detection.
5. Cross-exchange prices, volumes and spreads.
6. Real-time alerts.
7. DFIR investigation support using crypto-related evidence.

## Architecture
- Frontend: React + TypeScript + Vite
- Backend: FastAPI + WebSockets
- Storage: PostgreSQL-ready schema
- Cache/pub-sub: Redis-ready
- Market ingestion: Binance, Coinbase, Kraken, OKX adapters
- Blockchain adapters: Ethereum, Bitcoin, Solana, Tron, Polygon
- Detection: whale transfers, volume anomalies, exchange spreads, rapid fund movement

## Important
The application uses live public exchange feeds where available. Blockchain coverage is provider/node dependent. "Worldwide" means a scalable multi-exchange/multi-chain architecture, not literally every asset, exchange and blockchain transaction on Earth.

## Local run
Backend:
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

Set `VITE_API_URL=http://localhost:8000`.

## Render
### Backend Web Service
Root Directory: `backend`
Build: `pip install -r requirements.txt`
Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Frontend Static Site
Root Directory: `frontend`
Build: `npm install && npm run build`
Publish: `dist`
Environment:
`VITE_API_URL=https://YOUR-BACKEND.onrender.com`

### Optional PostgreSQL
Set `DATABASE_URL`.

### Optional Redis
Set `REDIS_URL`.

For continuous ingestion, run workers as separate Render Background Workers on a paid/always-on plan as appropriate.
