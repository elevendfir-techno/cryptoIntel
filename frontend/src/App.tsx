import React, { useEffect, useMemo, useState } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
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

      {page==="Blockchain" && <Info title="Blockchain Intelligence" text="Architecture prepared for Bitcoin, Ethereum, Solana, Tron and Polygon. Connect node/indexer credentials to ingest live blocks, transactions and token transfers."/>}
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
function WalletSearch(){const [a,setA]=useState("");const [r,setR]=useState<any>();return <section className="panel"><h2>Wallet Investigation</h2><input value={a} onChange={e=>setA(e.target.value)} placeholder="Enter wallet address"/><button className="primary" onClick={async()=>setR(await fetch(`${API}/api/wallets/${a||"demo"}`).then(x=>x.json()))}>Investigate</button>{r&&<pre>{JSON.stringify(r,null,2)}</pre>}</section>}
function FundFlow(){const [a,setA]=useState("");const [r,setR]=useState<any>();return <section className="panel"><h2>Fund Flow</h2><input value={a} onChange={e=>setA(e.target.value)} placeholder="Enter wallet address"/><button className="primary" onClick={async()=>setR(await fetch(`${API}/api/fundflow/${a||"demo"}`).then(x=>x.json()))}>Trace Flow</button>{r&&<pre>{JSON.stringify(r,null,2)}</pre>}</section>}
