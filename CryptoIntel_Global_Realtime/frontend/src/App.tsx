import React, { useEffect, useMemo, useState } from "react";

const API = "https://cryptointel-backend-fx16.onrender.com";
type Market = {symbol:string; exchange:string; price:number; volume:number; change24h:number; timestamp:string};
type Alert = {type:string; severity:string; message:string; timestamp:string};

export default function App(){
  const [markets,setMarkets]=useState<Market[]>([]);
  const [trades,setTrades]=useState<any[]>([]);
  const [alerts,setAlerts]=useState<Alert[]>([]);
  const [liveDetectionCount,setLiveDetectionCount]=useState(0);
  const [page,setPage]=useState("Overview");
  const [connected,setConnected]=useState(false);

  useEffect(()=>{

  const wsUrl=API.replace(/^http/,"ws")+"/ws/markets";

  const ws=new WebSocket(wsUrl);

  ws.onopen=()=>setConnected(true);

  ws.onclose=()=>setConnected(false);

  ws.onmessage=e=>{
    const d=JSON.parse(e.data);
    setMarkets(d.markets||[]);
    setAlerts(d.alerts||[]);
  };

  const loadTrades = async () => {
    try {
      const response = await fetch(`${API}/api/markets/trades`);
      const data = await response.json();

      if (response.ok) {
        setTrades(data || []);
      }
    } catch {
      // Keep previous trades if API is temporarily unavailable
    }
  };

  loadTrades();

  const interval = setInterval(loadTrades, 2000);

  return ()=>{
    ws.close();
    clearInterval(interval);
  };

},[]);
  useEffect(()=>{
  const loadDetectionCount = async () => {
    try {
      const response = await fetch(`${API}/api/detection`);
      const data = await response.json();

      if (response.ok) {
        setLiveDetectionCount(data.total_detections || 0);
      }
    } catch {
      // Keep previous count if API is temporarily unavailable
    }
  };

  loadDetectionCount();

  const interval = setInterval(loadDetectionCount, 10000);

  return () => clearInterval(interval);
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
          <Card
  title="ALERTS"
  value={String(liveDetectionCount)}
  sub="live detection events"
/>
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
      {page==="Detection" && <Detection markets={latest} trades={trades}/>}
      {page==="Alerts" && <section className="panel"><h2>Live Alerts</h2>{alerts.map((a,i)=><div className="alert big" key={i}><b>{a.severity}</b><span>{a.type}</span><span>{a.message}</span><small>{a.timestamp}</small></div>)}{!alerts.length&&<div className="empty">No active alerts.</div>}</section>}
      {page==="DFIR Cases" && <Info title="DFIR Investigation Workspace" text="Use crypto transaction timelines, wallet relationships, fund-flow graphs and exported evidence to support authorized investigations."/>}
    </main>
  </div>
}
function Card(p:any){return <div className="card"><small>{p.title}</small><strong>{p.value}</strong><span>{p.sub}</span></div>}
function MarketTable({data}:{data:Market[]}){return <div className="table"><div className="thead"><span>Exchange</span><span>Market</span><span>Price</span><span>24H</span><span>Volume</span><span>Status</span></div>{data.map((m,i)=><div className="tr" key={i}><span>{m.exchange}</span><b>{m.symbol}</b><span>${m.price.toLocaleString(undefined,{maximumFractionDigits:8})}</span><span className={m.change24h>=0?"up":"down"}>{m.change24h?m.change24h.toFixed(2)+"%":"—"}</span><span>{m.volume.toLocaleString(undefined,{maximumFractionDigits:2})}</span><span className="liveDot">● LIVE</span></div>)}</div>}
function Info({title,text}:{title:string;text:string}){return <section className="panel hero"><h2>{title}</h2><p>{text}</p></section>}
function Detection({
  markets,
  trades
}: {
  markets: Market[];
  trades: any[];
}) {

  const [detections, setDetections] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadDetections = async () => {
    try {
      setError("");

      const response = await fetch(
        `${API}/api/detection`
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Detection API unavailable"
        );
      }

      setDetections(
        data.detections || []
      );

    } catch (e: any) {

      setError(
        e.message || "Detection API unavailable"
      );

    } finally {

      setLoading(false);

    }
  };

  useEffect(() => {

    loadDetections();

    const interval = setInterval(
      loadDetections,
      10000
    );

    return () => clearInterval(interval);

  }, []);

  const high = detections.filter(
    d => d.severity === "HIGH"
  ).length;

  const medium = detections.filter(
    d => d.severity === "MEDIUM"
  ).length;

  const low = detections.filter(
    d => d.severity === "LOW"
  ).length;

  return (
    <>
      <section className="panel hero">

        <h2>
          Suspicious Activity Detection
        </h2>

        <p>
          Real-time rule-based detection using
          live cryptocurrency market feeds and
          Bitcoin blockchain data.
        </p>

        <div style={{
          marginTop: "12px",
          fontSize: "12px",
          color: "#777"
        }}>
          ● LIVE DETECTION ENGINE
        </div>

      </section>


      <section className="cards">

        <Card
          title="TOTAL DETECTIONS"
          value={String(detections.length)}
          sub="Live indicators"
        />

        <Card
          title="HIGH RISK"
          value={String(high)}
          sub="High severity"
        />

        <Card
          title="MEDIUM RISK"
          value={String(medium)}
          sub="Medium severity"
        />

        <Card
          title="LOW RISK"
          value={String(low)}
          sub="Low severity"
        />

      </section>


      <section className="panel">

        <h2>
          Detection Rules
        </h2>

        <div className="row">
          <b>PRICE ANOMALY</b>
          <span>
            Large 24H price movement
          </span>
          <small>
            ACTIVE
          </small>
        </div>

        <div className="row">
          <b>VOLUME SPIKE</b>
          <span>
            Unusually high trading volume
          </span>
          <small>
            ACTIVE
          </small>
        </div>

        <div className="row">
          <b>RAPID ACTIVITY</b>
          <span>
            High-frequency market activity
          </span>
          <small>
            ACTIVE
          </small>
        </div>

        <div className="row">
          <b>EXCHANGE SPREAD</b>
          <span>
            Unusual price difference between exchanges
          </span>
          <small>
            ACTIVE
          </small>
        </div>

        <div className="row">
          <b>LARGE TRANSFER</b>
          <span>
            Large Bitcoin transaction output
          </span>
          <small>
            ACTIVE
          </small>
        </div>

        <div className="row">
          <b>HIGH VALUE TRANSACTION</b>
          <span>
            Very large aggregate Bitcoin output value
          </span>
          <small>
            ACTIVE
          </small>
        </div>

        <div className="row">
          <b>MULTI-HOP MOVEMENT</b>
          <span>
            Wallet relationship tracing
          </span>
          <small>
            BLOCKCHAIN ANALYSIS
          </small>
        </div>

      </section>


      <section className="panel">

        <h2>
          Live Detection Results
        </h2>

        {loading && (
          <div className="empty">
            Loading live blockchain and market detections...
          </div>
        )}

        {error && (
          <div className="empty">
            {error}
          </div>
        )}

        {!loading && !error && detections.length === 0 && (
          <div className="empty">
            No detection events currently meet the configured thresholds.
          </div>
        )}

        {!loading && !error && detections.length > 0 && (

          <div className="table">

            <div className="thead">
              <span>Type</span>
              <span>Severity</span>
              <span>Asset</span>
              <span>Value</span>
              <span>Source</span>
              <span>Details</span>
            </div>


            {detections.map(
              (d: any, i: number) => (

                <div
                  className="tr"
                  key={`${d.txid || d.type}-${i}`}
                >

                  <b>
                    {d.type || "UNKNOWN"}
                  </b>


                  <span>
                    {d.severity || "UNKNOWN"}
                  </span>


                  <span>
                    {d.asset || "—"}
                  </span>


                  <span>
                    {d.value || "—"}
                  </span>


                  <span>
                    {d.source || "—"}
                  </span>


                  <span>
                    {d.reason || "—"}
                  </span>

                </div>

              )
            )}

          </div>

        )}

      </section>


      {!loading &&
        !error &&
        detections.some(d => d.txid) && (

        <section className="panel">

          <h2>
            Blockchain Detection Evidence
          </h2>

          <div className="table">

            <div className="thead">
              <span>Detection</span>
              <span>BTC Value</span>
              <span>TXID</span>
              <span>Block</span>
              <span>Network</span>
              <span>Source</span>
            </div>


            {detections
              .filter(d => d.txid)
              .map(
                (d: any, i: number) => (

                  <div
                    className="tr"
                    key={`blockchain-${d.txid}-${i}`}
                  >

                    <b>
                      {d.type}
                    </b>


                    <span>
                      {d.value || "—"}
                    </span>


                    <span
                      title={d.txid}
                      style={{
                        fontFamily: "monospace"
                      }}
                    >
                      {d.txid
                        ? d.txid.slice(0, 20) + "..."
                        : "—"}
                    </span>


                    <span
                      title={d.block}
                      style={{
                        fontFamily: "monospace"
                      }}
                    >
                      {d.block
                        ? d.block.slice(0, 20) + "..."
                        : "—"}
                    </span>


                    <span>
                      {d.network || "Bitcoin"}
                    </span>


                    <span>
                      {d.data_source ||
                        "Blockstream Esplora"}
                    </span>

                  </div>

                )
              )}

          </div>

        </section>

      )}


      <section className="panel hero">

        <h2>
          Investigation Note
        </h2>

        <p>
          Detection events are rule-based indicators
          generated from live market and blockchain
          data. A large transaction or unusual market
          movement does not by itself establish fraud,
          compromise, or criminal activity and should
          be investigated with additional context.
        </p>

      </section>

    </>
  );
}
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
function FundFlowGraph({nodes,edges}:{nodes:any[];edges:any[]}){
  const root=nodes.find(n=>n.hop===0) || nodes[0];
  const hop1=nodes.filter(n=>n.hop===1).slice(0,12);
  const hop2=nodes.filter(n=>n.hop===2).slice(0,24);

  return (
    <section className="panel">
      <h2>Fund Flow Graph</h2>
      <p>Visual representation of wallet relationships across traced hops.</p>

      <div style={{
        background:"#050505",
        border:"1px solid #222",
        borderRadius:"8px",
        padding:"20px",
        overflow:"auto"
      }}>
        <svg viewBox="0 0 1000 520" width="100%" height="520">

          {edges.slice(0,60).map((edge:any,i:number)=>{
            const sourceIndex=nodes.findIndex(n=>n.id===edge.source);
            const targetIndex=nodes.findIndex(n=>n.id===edge.target);

            if(sourceIndex<0 || targetIndex<0) return null;

            const sx=sourceIndex===0 ? 500 : 500+(sourceIndex%10)*35;
            const sy=sourceIndex===0 ? 260 : 120+(sourceIndex%10)*30;

            const tx=targetIndex===0 ? 500 : 500+(targetIndex%10)*35;
            const ty=targetIndex===0 ? 260 : 120+(targetIndex%10)*30;

            return (
              <line
                key={`${edge.txid}-${i}`}
                x1={sx}
                y1={sy}
                x2={tx}
                y2={ty}
                stroke="#555"
                strokeWidth="1"
              />
            );
          })}

          {root && (
            <g>
              <circle
                cx="500"
                cy="260"
                r="38"
                fill="#111"
                stroke="#fff"
                strokeWidth="3"
              />
              <text
                x="500"
                y="264"
                textAnchor="middle"
                fill="#fff"
                fontSize="12"
                fontWeight="bold"
              >
                ROOT
              </text>
            </g>
          )}

          {hop1.map((node:any,i:number)=>{
            const angle=(i/hop1.length)*Math.PI*2;

            const x=500+170*Math.cos(angle);
            const y=260+150*Math.sin(angle);

            return (
              <g key={node.id}>
                <circle
                  cx={x}
                  cy={y}
                  r="24"
                  fill="#111"
                  stroke="#fff"
                  strokeWidth="1.5"
                />
                <text
                  x={x}
                  y={y+4}
                  textAnchor="middle"
                  fill="#fff"
                  fontSize="9"
                  fontWeight="bold"
                >
                  H1
                </text>
              </g>
            );
          })}

          {hop2.map((node:any,i:number)=>{
            const angle=(i/hop2.length)*Math.PI*2;

            const x=500+350*Math.cos(angle);
            const y=260+210*Math.sin(angle);

            return (
              <g key={node.id}>
                <circle
                  cx={x}
                  cy={y}
                  r="20"
                  fill="#111"
                  stroke="#777"
                  strokeWidth="1"
                />
                <text
                  x={x}
                  y={y+4}
                  textAnchor="middle"
                  fill="#aaa"
                  fontSize="8"
                >
                  H2
                </text>
              </g>
            );
          })}

        </svg>
      </div>

      <div style={{
        display:"flex",
        gap:"20px",
        marginTop:"12px",
        color:"#777",
        fontSize:"10px"
      }}>
        <span>ROOT: {root?.id || "—"}</span>
        <span>HOP 1: {hop1.length}</span>
        <span>HOP 2: {hop2.length}</span>
      </div>
    </section>
  );
}
function FundFlow(){
  const [a,setA]=useState("");
  const [r,setR]=useState<any>(null);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState("");

  const traceFlow=async()=>{
    if(!a.trim()){
      setError("Please enter a Bitcoin wallet address.");
      return;
    }

    setLoading(true);
    setError("");
    setR(null);

    try{
      const response=await fetch(
        `${API}/api/fundflow/${encodeURIComponent(a.trim())}?network=bitcoin&hops=2`
      );

      const data=await response.json();

      if(!response.ok){
        throw new Error(data.detail || "Fund-flow investigation failed");
      }

      setR(data);
    }catch(e:any){
      setError(e.message || "Fund-flow investigation failed");
    }finally{
      setLoading(false);
    }
  };

  const btc=(sats:number)=>{
    return ((sats || 0)/100000000).toFixed(8)+" BTC";
  };

  return (
    <section className="panel">
      <h2>Bitcoin Fund Flow Investigation</h2>
      <p>
        Trace wallet relationships and transaction flows using live blockchain data.
      </p>

      <div className="searchBox">
        <input
          value={a}
          onChange={e=>setA(e.target.value)}
          onKeyDown={e=>{
            if(e.key==="Enter") traceFlow();
          }}
          placeholder="Enter Bitcoin wallet address"
        />

        <button
          className="primary"
          onClick={traceFlow}
          disabled={loading}
        >
          {loading ? "Tracing..." : "Trace Flow"}
        </button>
      </div>

      {error && <div className="empty">{error}</div>}

      {r && (
        <>
          <div className="cards">
            <Card
              title="NETWORK"
              value={r.network || "Bitcoin"}
              sub="Blockchain"
            />

            <Card
              title="WALLETS"
              value={String(r.wallet_count || r.nodes?.length || 0)}
              sub="Wallets identified"
            />

            <Card
              title="EDGES"
              value={String(r.edge_count || r.edges?.length || 0)}
              sub="Fund-flow relationships"
            />

            <Card
              title="TRANSACTIONS"
              value={String(r.transactions_scanned || 0)}
              sub="Transactions scanned"
            />
          </div>

          <section className="panel">
            <h2>Investigation Summary</h2>

            <div className="row">
              <b>Root Wallet</b>
              <span>{r.root}</span>
            </div>

            <div className="row">
              <b>Status</b>
              <span className="liveDot">
                ● {r.status || "LIVE"}
              </span>
            </div>

            <div className="row">
              <b>Hops Requested</b>
              <span>{r.hops_requested ?? "—"}</span>
            </div>

            <div className="row">
              <b>Hops Traced</b>
              <span>{r.hops_traced ?? "—"}</span>
            </div>

            <div className="row">
              <b>Data Source</b>
              <span>{r.source || "Blockchain API"}</span>
            </div>
          </section>
          <FundFlowGraph
  nodes={r.nodes || []}
  edges={r.edges || []}
/>

          <section className="panel">
            <h2>Fund Flow Transactions</h2>

            {r.edges?.length ? (
              <div className="table">

                <div className="thead">
                  <span>Source</span>
                  <span>Target</span>
                  <span>Amount</span>
                  <span>Type</span>
                  <span>TXID</span>
                  <span>Hop</span>
                </div>

                {r.edges.slice(0,50).map(
                  (edge:any,i:number)=>(
                    <div className="tr" key={`${edge.txid}-${i}`}>

                      <span>
                        {edge.source
                          ? edge.source.slice(0,12)+"..."
                          : "Unknown"}
                      </span>

                      <span>
                        {edge.target
                          ? edge.target.slice(0,12)+"..."
                          : "Unknown"}
                      </span>

                      <span>
                        {btc(edge.value_sats)}
                      </span>

                      <span className={
                        edge.type==="incoming"
                          ? "up"
                          : "down"
                      }>
                        {edge.type?.toUpperCase() || "UNKNOWN"}
                      </span>

                      <span title={edge.txid}>
                        {edge.txid
                          ? edge.txid.slice(0,16)+"..."
                          : "Unknown"}
                      </span>

                      <span>
                        {edge.hop ?? "—"}
                      </span>

                    </div>
                  )
                )}

              </div>
            ) : (
              <div className="empty">
                No fund-flow transactions found.
              </div>
            )}
          </section>

          <section className="panel">
            <h2>Wallet Network</h2>

            {r.nodes?.length ? (
              <div className="table">

                <div className="thead">
                  <span>Wallet</span>
                  <span>Type</span>
                  <span>Hop</span>
                </div>

                {r.nodes.slice(0,50).map(
                  (node:any,i:number)=>(
                    <div className="tr" key={node.id || i}>

                      <span title={node.id}>
                        {node.label ||
                          (node.id
                            ? node.id.slice(0,18)+"..."
                            : "Unknown")}
                      </span>

                      <span>
                        {node.type || "wallet"}
                      </span>

                      <span>
                        {node.hop ?? "—"}
                      </span>

                    </div>
                  )
                )}

              </div>
            ) : (
              <div className="empty">
                No wallet nodes found.
              </div>
            )}
          </section>
        </>
      )}
    </section>
  );
}
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