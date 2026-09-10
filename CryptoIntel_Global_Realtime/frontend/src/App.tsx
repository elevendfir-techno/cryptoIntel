import React, { useEffect, useMemo, useState } from "react";

const API = "https://cryptointel-backend-fx16.onrender.com";
type Market = {symbol:string; exchange:string; price:number; volume:number; change24h:number; timestamp:string};
type Alert = {type:string; severity:string; message:string; timestamp:string};

export default function App(){
  const [markets,setMarkets]=useState<Market[]>([]);
  const [trades,setTrades]=useState<any[]>([]);
  const [alerts,setAlerts]=useState<Alert[]>([]);
  const [page,setPage]=useState("Overview");
  const [connected,setConnected]=useState(false);

  useEffect(()=>{
    const wsUrl=API.replace(/^http/,"ws")+"/ws/markets";
    const ws=new WebSocket(wsUrl);
    ws.onopen=()=>setConnected(true);
    ws.onclose=()=>setConnected(false);
    ws.onmessage=e=>{const d=JSON.parse(e.data);setMarkets(d.markets||[]);setTrades(d.trades||[]);setAlerts(d.alerts||[])};
    return ()=>ws.close();
  },[]);

  const latest=useMemo(()=>{
    const map=new Map<string,Market>();
    markets.forEach(m=>map.set(m.exchange+"-"+m.symbol,m));
    return [...map.values()];
  },[markets]);

  const top=latest.slice(0,12);
  const price=(n:number)=>n? n.toLocaleString(undefined,{maximumFractionDigits:8}):"—";

  return <div className="app">
    <aside>
      <div className="logo">CRYPTO<span>INTEL</span></div>
      <div className="scope">GLOBAL REAL-TIME INTELLIGENCE</div>
      {["Overview","Live Markets","Blockchain","Wallet Investigation","Fund Flow","Detection","Alerts","DFIR Cases"].map(x=>
        <button className={page===x?"nav active":"nav"} onClick={()=>setPage(x)} key={x}>{x}</button>
      )}
      <div className="status"><i className={connected?"live":""}></i>{connected?"LIVE DATA CONNECTED":"CONNECTING..."}</div>
    </aside>
    <main>
      <header><div><h1>{page}</h1><p>Multi-exchange • Multi-chain • Real-time crypto intelligence</p></div><div className="badge">● {connected?"LIVE":"OFFLINE"}</div></header>

      {page==="Overview" && <>
        <section className="cards">
          <Card title="LIVE MARKETS" value={latest.length.toString()} sub="exchange feeds"/>
          <Card title="LIVE TRADES" value={trades.length.toString()} sub="recent stream"/>
          <Card title="ALERTS" value={alerts.length.toString()} sub="detection events"/>
          <Card title="NETWORKS" value="5+" sub="blockchain architecture"/>
        </section>
        <section className="panel"><h2>Global Market Feed</h2><MarketTable data={top}/></section>
        <section className="grid2">
          <section className="panel"><h2>Live Trades</h2>{trades.slice(0,10).map((t,i)=><div className="row" key={i}><b>{t.symbol}</b><span>{t.side}</span><span>${price(t.price)}</span><small>{t.exchange}</small></div>)}</section>
          <section className="panel"><h2>Detection Feed</h2>{alerts.slice(0,10).map((a,i)=><div className="alert" key={i}><b>{a.severity}</b><span>{a.message}</span></div>)}{!alerts.length&&<div className="empty">Detection engine ready — no current alerts.</div>}</section>
        </section>
      </>}

      {page==="Live Markets" && <section className="panel"><h2>Real-Time Exchange Markets</h2><MarketTable data={latest}/></section>}
      {page==="Blockchain" && <Blockchain />}
      {page==="Wallet Investigation" && <WalletSearch/>}
      {page==="Fund Flow" && <FundFlow/>}
      {page==="Detection" && <Info title="Suspicious Activity Detection" text="Rule engine supports large transfers, price/volume anomalies, exchange spreads and rapid multi-hop movement. Results are indicators, not automatic criminal attribution."/>}
      {page==="Alerts" && <section className="panel"><h2>Live Alerts</h2>{alerts.map((a,i)=><div className="alert big" key={i}><b>{a.severity}</b><span>{a.type}</span><span>{a.message}</span><small>{a.timestamp}</small></div>)}{!alerts.length&&<div className="empty">No active alerts.</div>}</section>}
      {page==="DFIR Cases" && <Info title="DFIR Investigation Workspace" text="Use crypto transaction timelines, wallet relationships, fund-flow graphs and exported evidence to support authorized investigations."/>}
    </main>
  </div>
}
function Card(p:any){return <div className="card"><small>{p.title}</small><strong>{p.value}</strong><span>{p.sub}</span></div>}
function MarketTable({data}:{data:Market[]}){return <div className="table"><div className="thead"><span>Exchange</span><span>Market</span><span>Price</span><span>24H</span><span>Volume</span><span>Status</span></div>{data.map((m,i)=><div className="tr" key={i}><span>{m.exchange}</span><b>{m.symbol}</b><span>${m.price.toLocaleString(undefined,{maximumFractionDigits:8})}</span><span className={m.change24h>=0?"up":"down"}>{m.change24h?m.change24h.toFixed(2)+"%":"—"}</span><span>{m.volume.toLocaleString(undefined,{maximumFractionDigits:2})}</span><span className="liveDot">● LIVE</span></div>)}</div>}
function Info({title,text}:{title:string;text:string}){return <section className="panel hero"><h2>{title}</h2><p>{text}</p></section>}
function WalletSearch(){
  const [a,setA]=useState("");
  const [r,setR]=useState<any>(null);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState("");

  const investigate=async()=>{
    if(!a.trim()){
      setError("Please enter a Bitcoin wallet address.");
      return;
    }

    setLoading(true);
    setError("");
    setR(null);

    try{
      const response=await fetch(
        `${API}/api/wallets/${encodeURIComponent(a.trim())}?network=bitcoin`
      );

      const data=await response.json();

      if(!response.ok){
        throw new Error(data.detail || "Wallet lookup failed");
      }

      setR(data);
    }catch(e:any){
      setError(e.message || "Wallet lookup failed");
    }finally{
      setLoading(false);
    }
  };

  const btc=(sats:number)=>{
    return (sats/100000000).toFixed(8)+" BTC";
  };

  return (
    <section className="panel">
      <h2>Bitcoin Wallet Investigation</h2>
      <p>Investigate Bitcoin addresses using live blockchain data.</p>

      <div className="searchBox">
        <input
          value={a}
          onChange={e=>setA(e.target.value)}
          onKeyDown={e=>{
            if(e.key==="Enter") investigate();
          }}
          placeholder="Enter Bitcoin wallet address"
        />

        <button
          className="primary"
          onClick={investigate}
          disabled={loading}
        >
          {loading ? "Investigating..." : "Investigate"}
        </button>
      </div>

      {error && <div className="empty">{error}</div>}

      {r && (
        <>
          <div className="cards">
            <Card
              title="NETWORK"
              value={r.network}
              sub="Blockchain"
            />

            <Card
              title="BALANCE"
              value={btc(r.balance?.balance || 0)}
              sub="Current calculated balance"
            />

            <Card
              title="TRANSACTIONS"
              value={String(r.activity?.confirmed_transactions || 0)}
              sub="Confirmed transactions"
            />

            <Card
              title="STATUS"
              value="LIVE"
              sub="Blockstream data"
            />
          </div>

          <section className="panel">
            <h2>Wallet Details</h2>

            <div className="row">
              <b>Address</b>
              <span>{r.address}</span>
            </div>

            <div className="row">
              <b>Balance</b>
              <span>{btc(r.balance?.balance || 0)}</span>
            </div>

            <div className="row">
              <b>Total Received</b>
              <span>{btc(r.balance?.funded || 0)}</span>
            </div>

            <div className="row">
              <b>Total Spent</b>
              <span>{btc(r.balance?.spent || 0)}</span>
            </div>
          </section>

          <section className="panel">
            <h2>Wallet Activity</h2>

            <div className="row">
              <b>Incoming Transactions</b>
              <span>{r.activity?.funded_transactions || 0}</span>
            </div>

            <div className="row">
              <b>Outgoing Transactions</b>
              <span>{r.activity?.spent_transactions || 0}</span>
            </div>

            <div className="row">
              <b>Confirmed Transactions</b>
              <span>{r.activity?.confirmed_transactions || 0}</span>
            </div>
          </section>

          <section className="panel">
            <h2>Transaction History</h2>

            {r.transactions?.length ? (
              <div className="table">
                <div className="thead">
                  <span>Transaction</span>
                  <span>Status</span>
                  <span>Block</span>
                  <span>Timestamp</span>
                </div>

                {r.transactions.slice(0,20).map(
                  (tx:any,i:number)=>(
                    <div className="tr" key={tx.txid || i}>
                      <span>
                        {tx.txid
                          ? tx.txid.slice(0,16)+"..."
                          : "Unknown"}
                      </span>

                      <span className="liveDot">
                        ● {tx.status?.confirmed
                          ? "CONFIRMED"
                          : "MEMPOOL"}
                      </span>

                      <span>
                        {tx.status?.block_height || "Pending"}
                      </span>

                      <span>
                        {tx.status?.block_time
                          ? new Date(
                              tx.status.block_time * 1000
                            ).toLocaleString()
                          : "Pending"}
                      </span>
                    </div>
                  )
                )}
              </div>
            ) : (
              <div className="empty">
                No transactions found.
              </div>
            )}
          </section>
        </>
      )}
    </section>
  );
}
function FundFlow(){const [a,setA]=useState("");const [r,setR]=useState<any>();return <section className="panel"><h2>Fund Flow</h2><input value={a} onChange={e=>setA(e.target.value)} placeholder="Enter wallet address"/><button className="primary" onClick={async()=>setR(await fetch(`${API}/api/fundflow/${a||"demo"}`).then(x=>x.json()))}>Trace Flow</button>{r&&<pre>{JSON.stringify(r,null,2)}</pre>}</section>}
function Blockchain(){
  const [blocks,setBlocks]=useState<any[]>([]);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");

  useEffect(()=>{
    fetch(`${API}/api/blockchain/bitcoin/blocks`)
      .then(r=>{
        if(!r.ok) throw new Error("Blockchain API unavailable");
        return r.json();
      })
      .then(d=>{
        setBlocks(d.blocks || []);
        setLoading(false);
      })
      .catch(e=>{
        setError(e.message);
        setLoading(false);
      });
  },[]);

  return (
    <section className="panel">
      <h2>Bitcoin Blockchain Intelligence</h2>
      <p>LIVE blockchain data from Bitcoin network</p>

      {loading && <div className="empty">Loading live blocks...</div>}

      {error && <div className="empty">{error}</div>}

      {!loading && !error && (
        <div className="table">
          <div className="thead">
            <span>Height</span>
            <span>Block Hash</span>
            <span>Transactions</span>
            <span>Size</span>
            <span>Weight</span>
            <span>Status</span>
          </div>

          {blocks.map((b,i)=>(
            <div className="tr" key={i}>
              <b>{b.height}</b>
              <span>{b.id.slice(0,18)}...</span>
              <span>{b.tx_count}</span>
              <span>{b.size?.toLocaleString()}</span>
              <span>{b.weight?.toLocaleString()}</span>
              <span className="liveDot">● LIVE</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}