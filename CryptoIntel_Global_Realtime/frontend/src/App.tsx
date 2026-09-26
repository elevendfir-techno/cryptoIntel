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
  useEffect(() => {

  const loadDetectionAndAlerts = async () => {

    try {

      // ============================
      // LIVE DETECTIONS
      // ============================

      const detectionResponse = await fetch(
        `${API}/api/detection`
      );

      const detectionData =
        await detectionResponse.json();

      if (detectionResponse.ok) {

        setLiveDetectionCount(
          detectionData.total_detections || 0
        );

      }


      // ============================
      // REAL ALERT ENGINE
      // ============================

      const alertResponse = await fetch(
        `${API}/api/alerts`
      );

      const alertData =
        await alertResponse.json();

      if (alertResponse.ok) {

        const realAlerts = (
          Array.isArray(alertData)
            ? alertData
            : alertData.alerts || []
        ).map((a: any) => ({

          type:
            a.detection_type ||
            a.alert_type ||
            a.type ||
            "RISK ALERT",

          severity:
            a.severity ||
            a.risk_level ||
            "UNKNOWN",

          message:
            a.reason ||
            a.message ||
            "Risk alert generated",

          timestamp:
            a.created_at ||
            a.timestamp ||
            new Date().toISOString()

        }));

        setAlerts(realAlerts);

      }

    } catch {

      // Keep previous live data if API
      // is temporarily unavailable

    }

  };


  loadDetectionAndAlerts();


  const interval = setInterval(
    loadDetectionAndAlerts,
    10000
  );


  return () =>
    clearInterval(interval);

}, []);

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
      {["Overview","Live Markets","Blockchain","Wallet Investigation","Fund Flow","Detection","Threat Intelligence","Alerts","DFIR Cases"].map(x=>
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
          <section className="panel">
  <h2>Detection Feed</h2>

  {alerts.slice(0,10).map((a,i)=>(
    <div className="alert" key={i}>
      <b>{a.severity}</b>
      <span>{a.type}</span>
      <span>{a.message}</span>
    </div>
  ))}

  {!alerts.length && (
    <div className="empty">
      Detection engine ready — no current alerts.
    </div>
  )}
</section>
</section>
      </>}

      {page==="Live Markets" && (
       <LiveMarkets
          markets={latest}
          trades={trades}
          connected={connected}
        />
      )}

      {page==="Blockchain" && <Blockchain />}
      {page==="Wallet Investigation" && <WalletSearch/>}
      {page==="Fund Flow" && <FundFlow/>}
      {page==="Detection" && <Detection markets={latest} trades={trades}/>}
      {page==="Threat Intelligence" && <ThreatIntelligence />}
      {page==="Alerts" && <section className="panel"><h2>Live Alerts</h2>{alerts.map((a,i)=><div className="alert big" key={i}><b>{a.severity}</b><span>{a.type}</span><span>{a.message}</span><small>{a.timestamp}</small></div>)}{!alerts.length&&<div className="empty">No active alerts.</div>}</section>}
      {page==="DFIR Cases" && <Info title="DFIR Investigation Workspace" text="Use crypto transaction timelines, wallet relationships, fund-flow graphs and exported evidence to support authorized investigations."/>}
    </main>
  </div>
}

function LiveMarkets({
  markets,
  trades,
  connected
}: {
  markets: Market[];
  trades: any[];
  connected: boolean;
}) {
  const exchanges = [
    ...new Set(
      markets
        .map(m => m.exchange)
        .filter(Boolean)
    )
  ];

  const symbols = [
    ...new Set(
      markets
        .map(m => m.symbol)
        .filter(Boolean)
    )
  ];

  const liveTrades = trades.slice(0, 12);

  return (
    <>
      <section className="panel hero">
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: "20px",
            flexWrap: "wrap"
          }}
        >
          <div>
            <h2>Market Intelligence Terminal</h2>
            <p>
              Real-time multi-exchange cryptocurrency
              market monitoring using live exchange feeds.
            </p>
          </div>

          <div
            style={{
              border: "1px solid #24533f",
              background: "rgba(56,224,146,0.04)",
              padding: "8px 12px",
              borderRadius: "5px",
              fontSize: "10px",
              color: connected ? "#62eca8" : "#ff7777",
              letterSpacing: "0.6px"
            }}
          >
            ● {connected ? "MARKET STREAM LIVE" : "MARKET STREAM OFFLINE"}
          </div>
        </div>
      </section>

      <section className="cards">
        <Card
          title="ACTIVE MARKETS"
          value={String(markets.length)}
          sub="Live market feeds"
        />

        <Card
          title="EXCHANGES"
          value={String(exchanges.length)}
          sub="Connected exchanges"
        />

        <Card
          title="TRADING PAIRS"
          value={String(symbols.length)}
          sub="Unique live pairs"
        />

        <Card
          title="LIVE TRADES"
          value={String(trades.length)}
          sub="Recent trade events"
        />
      </section>

      <section className="panel">
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: "12px",
            marginBottom: "5px"
          }}
        >
          <div>
            <h2>Live Exchange Intelligence</h2>
            <p
              style={{
                margin: "0",
                color: "#71818c",
                fontSize: "10px"
              }}
            >
              Current prices and market activity from
              connected exchange feeds.
            </p>
          </div>

          <span className="liveDot">
            ● REAL-TIME
          </span>
        </div>

        <MarketTable data={markets} />
      </section>

      <section className="panel">
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "5px"
          }}
        >
          <div>
            <h2>Real-Time Trade Stream</h2>
            <p
              style={{
                margin: "0",
                color: "#71818c",
                fontSize: "10px"
              }}
            >
              Latest trade events received from live
              exchange market streams.
            </p>
          </div>

          <span className="liveDot">
            ● STREAMING
          </span>
        </div>

        {liveTrades.length ? (
          <div className="table">

            <div
              className="thead"
              style={{
                gridTemplateColumns:
                  "1fr 1fr 1.3fr 1fr"
              }}
            >
              <span>Market</span>
              <span>Side</span>
              <span>Price</span>
              <span>Exchange</span>
            </div>

            {liveTrades.map(
              (trade: any, i: number) => {

                const side =
                  String(
                    trade.side || "UNKNOWN"
                  ).toUpperCase();

                return (
                  <div
                    className="tr"
                    key={`${trade.symbol}-${i}`}
                    style={{
                      gridTemplateColumns:
                        "1fr 1fr 1.3fr 1fr"
                    }}
                  >
                    <b>
                      {trade.symbol || "—"}
                    </b>

                    <span
                      className={
                        side === "BUY"
                          ? "up"
                          : side === "SELL"
                          ? "down"
                          : ""
                      }
                    >
                      {side}
                    </span>

                    <span
                      style={{
                        fontFamily: "monospace"
                      }}
                    >
                      {trade.price != null
                        ? `$${Number(
                            trade.price
                          ).toLocaleString(
                            undefined,
                            {
                              maximumFractionDigits: 8
                            }
                          )}`
                        : "—"}
                    </span>

                    <span>
                      {trade.exchange || "—"}
                    </span>
                  </div>
                );
              }
            )}

          </div>
        ) : (
          <div className="empty">
            No live trade events currently available.
          </div>
        )}
      </section>

      <section className="panel">
        <h2>Exchange Feed Status</h2>

        {exchanges.length ? (
          exchanges.map(
            (exchange, i) => (
              <div
                className="row"
                key={exchange || i}
              >
                <b>{exchange}</b>

                <span>
                  Live market feed
                </span>

                <small className="liveDot">
                  ● CONNECTED
                </small>
              </div>
            )
          )
        ) : (
          <div className="empty">
            No exchange feeds currently available.
          </div>
        )}
      </section>
    </>
  );
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
          data.detail ||
          "Detection API unavailable"
        );
      }

      setDetections(
        data.detections || []
      );

    } catch (e: any) {

      setError(
        e.message ||
        "Detection API unavailable"
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

    return () =>
      clearInterval(interval);

  }, []);


  /* =====================================================
     SEVERITY COUNTS
  ===================================================== */

  const high =
    detections.filter(
      d =>
        String(d.severity || "")
          .toUpperCase() === "HIGH"
    ).length;

  const medium =
    detections.filter(
      d =>
        String(d.severity || "")
          .toUpperCase() === "MEDIUM"
    ).length;

  const low =
    detections.filter(
      d =>
        String(d.severity || "")
          .toUpperCase() === "LOW"
    ).length;


  /* =====================================================
     FUND FLOW DETECTION
  ===================================================== */

  const isFundFlowDetection = (
    d: any
  ) => {

    return (
      d?.type ===
      "MULTI_HOP_FUND_FLOW"
    );

  };


  /* =====================================================
     SHORT ADDRESS
  ===================================================== */

  const shortAddress = (
    value: any
  ) => {

    if (!value) {
      return "—";
    }

    const text =
      String(value);

    if (text.length <= 22) {
      return text;
    }

    return (
      text.slice(0, 12) +
      "..." +
      text.slice(-6)
    );

  };


  /* =====================================================
     DETECTION DETAILS
  ===================================================== */

  const getDetectionDetails = (
    d: any
  ) => {

    if (
      isFundFlowDetection(d)
    ) {

      return (
        `Multi-hop fund flow: ` +
        `${d.hops ?? "—"} hops, ` +
        `${d.wallet_count ?? "—"} wallets, ` +
        `${d.edge_count ?? "—"} connections, ` +
        `${d.transactions_scanned ?? "—"} transactions`
      );

    }

    return (
      d.reason ||
      d.message ||
      "Detection event generated"
    );

  };


  return (
    <>

      {/* =================================================
          DETECTION HEADER
      ================================================= */}

      <section className="panel hero">

        <h2>
          Suspicious Activity Detection
        </h2>

        <p>
          Real-time rule-based detection using
          live cryptocurrency market feeds,
          blockchain activity and fund-flow analysis.
        </p>

        <div
          style={{
            marginTop: "12px",
            fontSize: "12px",
            color: "#777"
          }}
        >
          ● LIVE DETECTION ENGINE
        </div>

      </section>


      {/* =================================================
          DETECTION SUMMARY
      ================================================= */}

      <section className="cards">

        <Card
          title="TOTAL DETECTIONS"
          value={String(
            detections.length
          )}
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


      {/* =================================================
          DETECTION RULES
      ================================================= */}

      <section className="panel">

        <h2>
          Detection Rules
        </h2>

        <div className="row">

          <b>
            PRICE ANOMALY
          </b>

          <span>
            Large 24H price movement
          </span>

          <small>
            ACTIVE
          </small>

        </div>


        <div className="row">

          <b>
            VOLUME SPIKE
          </b>

          <span>
            Unusually high trading volume
          </span>

          <small>
            ACTIVE
          </small>

        </div>


        <div className="row">

          <b>
            RAPID ACTIVITY
          </b>

          <span>
            High-frequency market activity
          </span>

          <small>
            ACTIVE
          </small>

        </div>


        <div className="row">

          <b>
            EXCHANGE SPREAD
          </b>

          <span>
            Unusual price difference between exchanges
          </span>

          <small>
            ACTIVE
          </small>

        </div>


        <div className="row">

          <b>
            LARGE TRANSFER
          </b>

          <span>
            Large Bitcoin transaction output
          </span>

          <small>
            ACTIVE
          </small>

        </div>


        <div className="row">

          <b>
            HIGH VALUE TRANSACTION
          </b>

          <span>
            Very large aggregate Bitcoin output value
          </span>

          <small>
            ACTIVE
          </small>

        </div>


        <div className="row">

          <b>
            MULTI-HOP MOVEMENT
          </b>

          <span>
            Wallet relationship tracing across blockchain transactions
          </span>

          <small>
            ACTIVE
          </small>

        </div>

      </section>


      {/* =================================================
          LIVE DETECTION RESULTS
      ================================================= */}

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


        {!loading &&
          !error &&
          detections.length === 0 && (

          <div className="empty">
            No detection events currently meet the configured thresholds.
          </div>

        )}


        {!loading &&
          !error &&
          detections.length > 0 && (

          <div className="table">

            <div className="thead">

              <span>
                Type
              </span>

              <span>
                Severity
              </span>

              <span>
                Network
              </span>

              <span>
                Asset / Root
              </span>

              <span>
                Source
              </span>

              <span>
                Details
              </span>

            </div>


            {detections.map(
              (
                d: any,
                i: number
              ) => {

                const fundFlow =
                  isFundFlowDetection(d);

                return (

                  <div
                    className="tr"
                    key={
                      `${d.txid || d.type}-${i}`
                    }
                  >

                    <b>
                      {d.type ||
                        "UNKNOWN"}
                    </b>


                    <span>
                      {d.severity ||
                        "UNKNOWN"}
                    </span>


                    <span>
                      {d.network ||
                        "—"}
                    </span>


                    <span
                      title={
                        fundFlow
                          ? (
                              d.root_wallet ||
                              d.address ||
                              ""
                            )
                          : ""
                      }
                      style={
                        fundFlow
                          ? {
                              fontFamily:
                                "monospace"
                            }
                          : {}
                      }
                    >

                      {fundFlow
                        ? shortAddress(
                            d.root_wallet ||
                            d.address
                          )
                        : (
                            d.asset ||
                            "—"
                          )}

                    </span>


                    <span>
                      {d.source ||
                        d.data_source ||
                        "—"}
                    </span>


                    <span>
                      {getDetectionDetails(
                        d
                      )}
                    </span>

                  </div>

                );

              }
            )}

          </div>

        )}

      </section>


      {/* =================================================
          FUND FLOW EVIDENCE
      ================================================= */}

      {!loading &&
        !error &&
        detections.some(
          d =>
            isFundFlowDetection(d)
        ) && (

        <section className="panel">

          <h2>
            Fund Flow Detection Evidence
          </h2>

          <p>
            Multi-hop fund-flow detections generated
            from completed live wallet relationship analysis.
          </p>


          <div className="table">

            <div className="thead">

              <span>
                Network
              </span>

              <span>
                Root Wallet
              </span>

              <span>
                Hops
              </span>

              <span>
                Wallets
              </span>

              <span>
                Connections
              </span>

              <span>
                Transactions
              </span>

            </div>


            {detections
              .filter(
                d =>
                  isFundFlowDetection(d)
              )
              .map(
                (
                  d: any,
                  i: number
                ) => (

                  <div
                    className="tr"
                    key={
                      `fundflow-${i}-${d.root_wallet || d.address || "unknown"}`
                    }
                  >

                    <span>
                      {d.network ||
                        "Unknown"}
                    </span>


                    <span
                      title={
                        d.root_wallet ||
                        d.address ||
                        ""
                      }
                      style={{
                        fontFamily:
                          "monospace",
                        wordBreak:
                          "break-all"
                      }}
                    >

                      {shortAddress(
                        d.root_wallet ||
                        d.address
                      )}

                    </span>


                    <span>
                      {d.hops ??
                        "—"}
                    </span>


                    <span>
                      {d.wallet_count ??
                        "—"}
                    </span>


                    <span>
                      {d.edge_count ??
                        "—"}
                    </span>


                    <span>
                      {d.transactions_scanned ??
                        "—"}
                    </span>

                  </div>

                )
              )}

          </div>


          {/* FUND FLOW MESSAGE */}

          {detections
            .filter(
              d =>
                isFundFlowDetection(d)
            )
            .slice(0, 10)
            .map(
              (
                d: any,
                i: number
              ) => (

                <div
                  className="row"
                  key={
                    `fundflow-message-${i}`
                  }
                  style={{
                    marginTop: "8px"
                  }}
                >

                  <b>
                    Detection
                  </b>

                  <span>
                    {d.message ||
                      "Multi-hop fund-flow activity detected."}
                  </span>

                  <small>
                    {d.status ||
                      "LIVE"}
                  </small>

                </div>

              )
            )}

        </section>

      )}


      {/* =================================================
          BLOCKCHAIN DETECTION EVIDENCE
      ================================================= */}

      {!loading &&
        !error &&
        detections.some(
          d =>
            d.txid
        ) && (

        <section className="panel">

          <h2>
            Blockchain Detection Evidence
          </h2>

          <div className="table">

            <div className="thead">

              <span>
                Detection
              </span>

              <span>
                BTC Value
              </span>

              <span>
                TXID
              </span>

              <span>
                Block
              </span>

              <span>
                Network
              </span>

              <span>
                Source
              </span>

            </div>


            {detections
              .filter(
                d =>
                  d.txid
              )
              .map(
                (
                  d: any,
                  i: number
                ) => (

                  <div
                    className="tr"
                    key={
                      `blockchain-${d.txid}-${i}`
                    }
                  >

                    <b>
                      {d.type}
                    </b>


                    <span>
                      {d.value ||
                        "—"}
                    </span>


                    <span
                      title={
                        d.txid
                      }
                      style={{
                        fontFamily:
                          "monospace"
                      }}
                    >

                      {d.txid
                        ? d.txid.slice(
                            0,
                            20
                          ) + "..."
                        : "—"}

                    </span>


                    <span
                      title={
                        d.block
                      }
                      style={{
                        fontFamily:
                          "monospace"
                      }}
                    >

                      {d.block !== undefined &&
                      d.block !== null
                       ? String(d.block).slice(
                           0,
                           20
                         ) + "..."
                       : "—"}

                    </span>


                    <span>
                      {d.network ||
                        "Bitcoin"}
                    </span>


                    <span>
                      {d.data_source ||
                        "Blockchain.com Blockchain Data API"}
                    </span>

                  </div>
                )
              )}

          </div>

        </section>

      )}


      {/* =================================================
          INVESTIGATION NOTE
      ================================================= */}

      <section className="panel hero">

        <h2>
          Investigation Note
        </h2>

        <p>
          Detection events are rule-based indicators
          generated from live market, blockchain and
          fund-flow data. A large transaction, unusual
          market movement, or multi-hop wallet pattern
          does not by itself establish fraud, compromise,
          or criminal activity and should be investigated
          with additional context.
        </p>

      </section>

    </>
  );
}

function WalletSearch() {
  const [network, setNetwork] = useState<"bitcoin" | "ethereum">("bitcoin");
  const [address, setAddress] = useState("");
  const [wallet, setWallet] = useState<any>(null);
  const [transactions, setTransactions] = useState<any[]>([]);
  const [tokens, setTokens] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [nextPageParams, setNextPageParams] = useState<any>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [bitcoinPage, setBitcoinPage] = useState(1);

  const investigate = async () => {
    const value = address.trim();

    if (!value) {
      setError(
        network === "bitcoin"
          ? "Please enter a Bitcoin wallet address."
          : "Please enter an Ethereum wallet address."
      );
      return;
    }

    setLoading(true);
    setError("");
    setWallet(null);
    setTransactions([]);
    setTokens([]);
    setNextPageParams(null);
    setBitcoinPage(1);

    try {
      if (network === "bitcoin") {
        const response = await fetch(
          `${API}/api/wallets/${encodeURIComponent(value)}?network=bitcoin&page=1&limit=100`
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            data.detail || "Bitcoin wallet lookup failed."
          );
        }

        setWallet({
          type: "bitcoin",
          raw: data
        });

        setTransactions(data.transactions || []);
      }

      if (network === "ethereum") {
        const [walletResponse, txResponse, tokenResponse] =
          await Promise.all([
            fetch(
              `${API}/api/blockchain/ethereum/wallet/${encodeURIComponent(
                value
              )}`
            ),
            fetch(
              `${API}/api/blockchain/ethereum/wallet/${encodeURIComponent(
                value
              )}/transactions`
            ),
            fetch(
              `${API}/api/blockchain/ethereum/wallet/${encodeURIComponent(
                value
              )}/tokens`
            )
          ]);

        const walletData = await walletResponse.json();
        const txData = txResponse.ok
          ? await txResponse.json()
          : {};
        const tokenData = tokenResponse.ok
          ? await tokenResponse.json()
          : {};

        if (!walletResponse.ok) {
          throw new Error(
            walletData.detail ||
            "Ethereum wallet lookup failed."
          );
        }

        setWallet({
          type: "ethereum",
          raw: walletData
        });

        setTransactions(
          txData.transactions || []
        );

        setNextPageParams(
        txData.next_page_params || null
        );

        setTokens(
          tokenData.token_transfers || []
        );
      }

    } catch (e: any) {
      setError(
        e.message ||
        "Wallet investigation failed."
      );
    } finally {
      setLoading(false);
    }
  };
  
  const loadMoreTransactions = async () => {
    if (
      network !== "ethereum" ||
      !address.trim() ||
      !nextPageParams ||
      loadingMore
    ) {
      return;
    }

    setLoadingMore(true);
    setError("");

    try {
      const query = new URLSearchParams();

      Object.entries(nextPageParams).forEach(
        ([key, value]) => {
          if (
            value !== null &&
            value !== undefined
          ) {
            query.append(
              key,
              String(value)
            );
          }
        }
      );

      const response = await fetch(
        `${API}/api/blockchain/ethereum/wallet/${encodeURIComponent(
          address.trim()
        )}/transactions?${query.toString()}`
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
          "Failed to load more transactions."
        );
      }

      setTransactions(prev => [
        ...prev,
        ...(data.transactions || [])
      ]);

      setNextPageParams(
        data.next_page_params || null
      );

    } catch (e: any) {
      setError(
        e.message ||
        "Failed to load more transactions."
      );
    } finally {
      setLoadingMore(false);
    }
  };

    const loadBitcoinPage = async (page: number) => {
    if (
      network !== "bitcoin" ||
      !address.trim() ||
      loading
    ) {
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `${API}/api/wallets/${encodeURIComponent(
          address.trim()
        )}?network=bitcoin&page=${page}&limit=100`
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
          "Bitcoin wallet lookup failed."
        );
      }

      setWallet({
        type: "bitcoin",
        raw: data
      });

      setTransactions(
        data.transactions || []
      );

      setBitcoinPage(page);

    } catch (e: any) {
      setError(
        e.message ||
        "Bitcoin wallet lookup failed."
      );
    } finally {
      setLoading(false);
    }
  };
  const btc = (sats: number) => {
  
    return (
      ((sats || 0) / 100000000).toFixed(8) +
      " BTC"
    );
  };

  const ethWallet = wallet?.raw?.wallet;
  const btcWallet = wallet?.raw;

  return (
    <section className="panel">

      <h2>
        Wallet Investigation
      </h2>

      <p>
        Investigate live blockchain wallet activity,
        transactions and token transfers.
      </p>


      {/* NETWORK SELECTOR */}

      <div
        style={{
          display: "flex",
          gap: "8px",
          marginBottom: "14px"
        }}
      >

        <button
          className={
            network === "bitcoin"
              ? "primary"
              : "nav"
          }
          onClick={() => {
            setNetwork("bitcoin");
            setAddress("");
            setWallet(null);
            setTransactions([]);
            setTokens([]);
            setError("");
          }}
        >
          Bitcoin
        </button>

        <button
          className={
            network === "ethereum"
              ? "primary"
              : "nav"
          }
          onClick={() => {
            setNetwork("ethereum");
            setAddress("");
            setWallet(null);
            setTransactions([]);
            setTokens([]);
            setError("");
          }}
        >
          Ethereum
        </button>

      </div>


      {/* SEARCH */}

      <div className="searchBox">

        <input
          value={address}
          onChange={e =>
            setAddress(e.target.value)
          }
          onKeyDown={e => {
            if (e.key === "Enter") {
              investigate();
            }
          }}
          placeholder={
            network === "bitcoin"
              ? "Enter Bitcoin wallet address"
              : "Enter Ethereum wallet address"
          }
        />

        <button
          className="primary"
          onClick={investigate}
          disabled={loading}
        >
          {loading
            ? "Investigating..."
            : "Investigate"}
        </button>

      </div>


      {/* ERROR */}

      {error && (
        <div className="empty">
          {error}
        </div>
      )}


      {/* =================================================
          BITCOIN RESULTS
      ================================================= */}

      {wallet?.type === "bitcoin" && btcWallet && (
        <>

          <div className="cards">

            <Card
              title="NETWORK"
              value="Bitcoin"
              sub="Blockchain"
            />

            <Card
              title="BALANCE"
              value={btc(
                btcWallet.balance?.balance || 0
              )}
              sub="Current balance"
            />

            <Card
              title="TRANSACTIONS"
              value={String(
                btcWallet.activity
                  ?.confirmed_transactions || 0
              )}
              sub="Confirmed transactions"
            />

            <Card
              title="STATUS"
              value="LIVE"
              sub="Blockchain data"
            />

          </div>


          <section className="panel">

            <h2>
              Bitcoin Wallet Details
            </h2>

            <div className="row">
              <b>Address</b>
              <span>
                {btcWallet.address}
              </span>
            </div>

            <div className="row">
              <b>Balance</b>
              <span>
                {btc(
                  btcWallet.balance?.balance || 0
                )}
              </span>
            </div>

            <div className="row">
              <b>Total Received</b>
              <span>
                {btc(
                  btcWallet.balance?.funded || 0
                )}
              </span>
            </div>

            <div className="row">
              <b>Total Spent</b>
              <span>
                {btc(
                  btcWallet.balance?.spent || 0
                )}
              </span>
            </div>

            <div className="row">
              <b>Incoming Transactions</b>
              <span>
                {btcWallet.activity
                  ?.funded_transactions || 0}
              </span>
            </div>

            <div className="row">
              <b>Outgoing Transactions</b>
              <span>
                {btcWallet.activity
                  ?.spent_transactions || 0}
              </span>
            </div>

            <div className="row">
              <b>Confirmed Transactions</b>
              <span>
                {btcWallet.activity
                  ?.confirmed_transactions || 0}
              </span>
            </div>

            <div className="row">
              <b>Status</b>
              <span className="liveDot">
                ● LIVE
              </span>
            </div>

          </section>


          <section className="panel">

            <h2>
              Bitcoin Transaction History
            </h2>

            {transactions.length ? (

  <>

    <div className="table">

      <div className="thead">
        <span>Transaction</span>
        <span>Status</span>
        <span>Block</span>
        <span>Timestamp</span>
      </div>

      {transactions.map(
        (tx: any, i: number) => {

          const txHash =
            tx.hash ||
            tx.txid ||
            "";

          const blockHeight =
            tx.block_height ??
            tx.status?.block_height ??
            null;

          const blockTime =
            tx.time ??
            tx.block_time ??
            tx.status?.block_time ??
            null;

          const confirmed =
            blockHeight !== null ||
            tx.confirmed === true ||
            tx.status?.confirmed === true;

          return (
            <div
              className="tr"
              key={txHash || i}
            >

              <span
                title={txHash}
                style={{
                  fontFamily: "monospace"
                }}
              >
                {txHash
                  ? txHash.slice(0, 16) + "..."
                  : "Unknown"}
              </span>

              <span className="liveDot">
                ●{" "}
                {confirmed
                  ? "CONFIRMED"
                  : "UNCONFIRMED"}
              </span>

              <span>
                {blockHeight !== null
                  ? blockHeight
                  : "Pending"}
              </span>

              <span>
                {blockTime
                  ? new Date(
                      blockTime * 1000
                    ).toLocaleString()
                  : "Unknown"}
              </span>

            </div>
          );
        }
      )}

    </div>

    {/* BITCOIN PAGINATION */}

    <div
      style={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        gap: "12px",
        marginTop: "16px"
      }}
    >

      <button
        className="nav"
        onClick={() =>
          loadBitcoinPage(bitcoinPage - 1)
        }
        disabled={
          bitcoinPage === 1 ||
          loading
        }
      >
        Previous
      </button>

      <span>
        Page {bitcoinPage} of{" "}
        {Math.ceil(
          (wallet?.raw?.pagination?.total || 0) / 100
        )}
      </span>

      <button
        className="primary"
        onClick={() =>
          loadBitcoinPage(bitcoinPage + 1)
        }
        disabled={
          loading ||
          bitcoinPage >=
            Math.ceil(
              (wallet?.raw?.pagination?.total || 0) / 100
            )
        }
      >
        Next
      </button>

    </div>

  </>

) : (

  <div className="empty">
    No Bitcoin transactions found.
  </div>

)}

          </section>

        </>
      )}


      {/* =================================================
          ETHEREUM RESULTS
      ================================================= */}

      {wallet?.type === "ethereum" &&
        ethWallet && (
        <>

          <div className="cards">

            <Card
              title="ETH BALANCE"
              value={`${Number(
                ethWallet.balance_eth || 0
              ).toFixed(6)} ETH`}
              sub="Current Mainnet balance"
            />

            <Card
              title="TRANSACTIONS SENT"
              value={String(
                ethWallet.transaction_count ?? 0
              )}
              sub="Account nonce"
            />

            <Card
              title="TRANSACTION HISTORY"
              value={String(
                transactions.length
              )}
              sub="Indexed transactions"
            />

            <Card
              title="TOKEN TRANSFERS"
              value={String(
                tokens.length
              )}
              sub="ERC-20 transfers"
            />

          </div>


          <section className="panel">

            <h2>
              Ethereum Wallet Details
            </h2>

            <div className="row">
              <b>Address</b>
              <span
                style={{
                  fontFamily: "monospace",
                  wordBreak: "break-all"
                }}
              >
                {ethWallet.address}
              </span>
            </div>

            <div className="row">
              <b>ETH Balance</b>
              <span>
                {ethWallet.balance_eth} ETH
              </span>
            </div>

            <div className="row">
              <b>Balance Wei</b>
              <span>
                {ethWallet.balance_wei}
              </span>
            </div>

            <div className="row">
              <b>Transaction Count</b>
              <span>
                {ethWallet.transaction_count}
              </span>
            </div>

            <div className="row">
              <b>Network</b>
              <span>
                Ethereum Mainnet
              </span>
            </div>

            <div className="row">
              <b>Data Source</b>
              <span>
                PublicNode Ethereum JSON-RPC
              </span>
            </div>

            <div className="row">
              <b>Status</b>
              <span className="liveDot">
                ● LIVE
              </span>
            </div>

          </section>


          {/* ETH TRANSACTION HISTORY */}

<section className="panel">

  <h2>
    Ethereum Transaction History
  </h2>

  {transactions.length ? (

    <>
      <div className="table">

        <div className="thead">
          <span>Direction</span>
          <span>Transaction</span>
          <span>From</span>
          <span>To</span>
          <span>Value</span>
          <span>Status</span>
        </div>

        {transactions.map(
          (tx: any, i: number) => (

            <div
              className="tr"
              key={tx.hash || i}
            >

              <span>
                <b
                  className={
                    tx.direction === "INCOMING"
                      ? "up"
                      : "down"
                  }
                >
                  {tx.direction || "UNKNOWN"}
                </b>
              </span>

              <span
                title={tx.hash}
                style={{
                  fontFamily: "monospace"
                }}
              >
                {tx.hash
                  ? tx.hash.slice(0, 10) +
                    "..." +
                    tx.hash.slice(-8)
                  : "—"}
              </span>

              <span
                title={tx.from}
                style={{
                  fontFamily: "monospace"
                }}
              >
                {tx.from
                  ? tx.from.slice(0, 8) +
                    "..." +
                    tx.from.slice(-6)
                  : "—"}
              </span>

              <span
                title={tx.to}
                style={{
                  fontFamily: "monospace"
                }}
              >
                {tx.to
                  ? tx.to.slice(0, 8) +
                    "..." +
                    tx.to.slice(-6)
                  : "—"}
              </span>

              <span>
                {tx.value ?? "0"}
              </span>

              <span>
                <b
                  className={
                    tx.success
                      ? "up"
                      : "down"
                  }
                >
                  {tx.success
                    ? "SUCCESS"
                    : "FAILED"}
                </b>
              </span>

            </div>

          )
        )}

      </div>

      {nextPageParams && (

        <div
          style={{
            display: "flex",
            justifyContent: "center",
            marginTop: "16px"
          }}
        >

          <button
            className="primary"
            onClick={loadMoreTransactions}
            disabled={loadingMore}
          >

            {loadingMore
              ? "Loading..."
              : "Load More Transactions"}

          </button>

        </div>

      )}

    </>

  ) : (

    <div className="empty">
      No Ethereum transaction history returned.
    </div>

  )}

</section>

        {/* ERC-20 */}

<section className="panel erc-panel">

  <h2>
    ERC-20 Token Transfers
  </h2>

  {tokens.length ? (

    <div className="table">

      <div className="thead">
        <span>Direction</span>
        <span>Token</span>
        <span>Symbol</span>
        <span>Amount</span>
        <span>From</span>
        <span>To</span>
        <span>Transaction</span>
      </div>

      {tokens
        .slice(0, 50)
        .map((tx: any, i: number) => {

          const decimals = Number(
            tx.decimals ?? 18
          );

          const rawValue = String(
            tx.value ?? "0"
          );

          let amount = "0";

          try {
            if (
              /^\d+$/.test(rawValue) &&
              decimals >= 0 &&
              decimals <= 36
            ) {
              const value =
                BigInt(rawValue);

              const divisor =
                10n ** BigInt(decimals);

              const whole =
                value / divisor;

              const fraction =
                value % divisor;

              if (fraction === 0n) {
                amount =
                  whole.toString();
              } else {
                const fractionText =
                  fraction
                    .toString()
                    .padStart(
                      decimals,
                      "0"
                    )
                    .replace(
                      /0+$/,
                      ""
                    );

                amount =
                  `${whole}.${fractionText}`;
              }
            } else {
              amount = rawValue;
            }
          } catch {
            amount = rawValue;
          }

          const direction =
            tx.direction === "INCOMING"
              ? "INCOMING"
              : tx.direction === "OUTGOING"
              ? "OUTGOING"
              : "UNKNOWN";

          const shortAddress = (
            value: string
          ) =>
            value
              ? value.slice(0, 8) +
                "..." +
                value.slice(-6)
              : "—";

          const shortHash = (
            value: string
          ) =>
            value
              ? value.slice(0, 10) +
                "..." +
                value.slice(-8)
              : "—";

          return (
            <div
              className="tr"
              key={
                tx.hash ||
                `${tx.token_address}-${i}`
              }
            >

              <span>
                <b
                  className={
                    direction === "INCOMING"
                      ? "up"
                      : direction === "OUTGOING"
                      ? "down"
                      : ""
                  }
                >
                  {direction}
                </b>
              </span>

              <span>
                {tx.token || "Unknown"}
              </span>

              <b>
                {tx.symbol || "—"}
              </b>

              <span
                title={`Raw value: ${rawValue}`}
                style={{
                  fontFamily: "monospace"
                }}
              >
                {amount}{" "}
                {tx.symbol || ""}
              </span>

              <span
                title={tx.from || ""}
                style={{
                  fontFamily: "monospace"
                }}
              >
                {shortAddress(
                  tx.from
                )}
              </span>

              <span
                title={tx.to || ""}
                style={{
                  fontFamily: "monospace"
                }}
              >
                {shortAddress(
                  tx.to
                )}
              </span>

              <span
                title={tx.hash || ""}
                style={{
                  fontFamily: "monospace"
                }}
              >
                {shortHash(
                  tx.hash
                )}
              </span>

            </div>
          );
        })}

    </div>

  ) : (

    <div className="empty">
      No ERC-20 token transfers found.
    </div>

            )}

          </section>

        </>
      )}

    </section>
  );
}
function FundFlowGraph({
  nodes,
  edges,
  edges_data
}: {
  nodes: any[];
  edges: any[];
  edges_data?: any[];
}) {
  const root =
    nodes.find((n: any) => n.hop === 0) ||
    nodes[0];

  const hop1 = nodes
    .filter((n: any) => n.hop === 1)
    .slice(0, 12);

  const hop2 = nodes
    .filter((n: any) => n.hop === 2)
    .slice(0, 24);

  const graphEdges =
    edges.length > 0
      ? edges
      : (edges_data || []);

  const positions: {
    [key: string]: {
      x: number;
      y: number;
    };
  } = {};

  if (root && root.id) {
    positions[String(root.id)] = {
      x: 500,
      y: 260
    };
  }

  hop1.forEach((node: any, i: number) => {
    if (!node.id) return;

    const angle =
      (i / Math.max(hop1.length, 1)) *
      Math.PI *
      2;

    positions[String(node.id)] = {
      x: 500 + 170 * Math.cos(angle),
      y: 260 + 150 * Math.sin(angle)
    };
  });

  hop2.forEach((node: any, i: number) => {
    if (!node.id) return;

    const angle =
      (i / Math.max(hop2.length, 1)) *
      Math.PI *
      2;

    positions[String(node.id)] = {
      x: 500 + 350 * Math.cos(angle),
      y: 260 + 210 * Math.sin(angle)
    };
  });

  return (
    <section className="panel">

      <h2>Fund Flow Graph</h2>

      <p>
        Visual representation of wallet relationships across traced hops.
      </p>

      <div
        style={{
          background: "#050505",
          border: "1px solid #222",
          borderRadius: "8px",
          padding: "20px",
          overflow: "auto"
        }}
      >

        <svg
          viewBox="0 0 1000 520"
          width="100%"
          height="520"
        >

          {/* CONNECTIONS */}

          {graphEdges
            .slice(0, 60)
            .map((edge: any, i: number) => {

              const source =
                positions[String(edge.source)];

              const target =
                positions[String(edge.target)];

              if (!source || !target) {
                return null;
              }

              return (
                <line
                  key={
                    `${edge.txid || edge.hash || i}-${i}`
                  }
                  x1={source.x}
                  y1={source.y}
                  x2={target.x}
                  y2={target.y}
                  stroke="#555"
                  strokeWidth="1.5"
                />
              );
            })}


          {/* ROOT */}

          {root && root.id && (
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
                y="255"
                textAnchor="middle"
                fill="#fff"
                fontSize="12"
                fontWeight="bold"
              >
                ROOT
              </text>

              <text
                x="500"
                y="270"
                textAnchor="middle"
                fill="#aaa"
                fontSize="8"
              >
                {String(root.id).slice(0, 8)}...
              </text>

            </g>
          )}


          {/* HOP 1 */}

          {hop1.map((node: any) => {

            const position =
              positions[String(node.id)];

            if (!position) {
              return null;
            }

            return (
              <g key={String(node.id)}>

                <circle
                  cx={position.x}
                  cy={position.y}
                  r="24"
                  fill="#111"
                  stroke="#fff"
                  strokeWidth="1.5"
                />

                <text
                  x={position.x}
                  y={position.y - 2}
                  textAnchor="middle"
                  fill="#fff"
                  fontSize="9"
                  fontWeight="bold"
                >
                  H1
                </text>

                <text
                  x={position.x}
                  y={position.y + 9}
                  textAnchor="middle"
                  fill="#aaa"
                  fontSize="7"
                >
                  {String(node.id).slice(0, 6)}...
                </text>

              </g>
            );
          })}


          {/* HOP 2 */}

          {hop2.map((node: any) => {

            const position =
              positions[String(node.id)];

            if (!position) {
              return null;
            }

            return (
              <g key={String(node.id)}>

                <circle
                  cx={position.x}
                  cy={position.y}
                  r="20"
                  fill="#111"
                  stroke="#777"
                  strokeWidth="1"
                />

                <text
                  x={position.x}
                  y={position.y - 1}
                  textAnchor="middle"
                  fill="#aaa"
                  fontSize="8"
                >
                  H2
                </text>

                <text
                  x={position.x}
                  y={position.y + 9}
                  textAnchor="middle"
                  fill="#777"
                  fontSize="6"
                >
                  {String(node.id).slice(0, 6)}...
                </text>

              </g>
            );
          })}

        </svg>

      </div>


      {/* GRAPH SUMMARY */}

      <div
        style={{
          display: "flex",
          gap: "20px",
          marginTop: "12px",
          color: "#777",
          fontSize: "10px",
          flexWrap: "wrap"
        }}
      >

        <span>
          ROOT: {root?.id || "—"}
        </span>

        <span>
          HOP 1: {hop1.length}
        </span>

        <span>
          HOP 2: {hop2.length}
        </span>

        <span>
          EDGES: {graphEdges.length}
        </span>

      </div>

    </section>
  );
}

function ThreatIntelligence() {

  const [indicatorType, setIndicatorType] =
    useState("WALLET_ADDRESS");

  const [indicator, setIndicator] =
    useState("");

  const [source, setSource] =
    useState("Manual Threat Intelligence Input");

  const [confidence, setConfidence] =
    useState("HIGH");

  const [severity, setSeverity] =
    useState("HIGH");

  const [network, setNetwork] =
    useState("Ethereum");

  const [result, setResult] =
    useState<any>(null);

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState("");

  const submitThreatInput = async () => {

    if (!indicator.trim()) {
      setError("Please enter an indicator.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    try {

      const response = await fetch(
        `${API}/api/threat-inputs`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            indicator_type: indicatorType,
            indicator: indicator.trim(),
            source,
            confidence,
            severity,
            network
          })
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data?.detail ||
          "Threat input submission failed."
        );
      }

      setResult(data);

    } catch (err: any) {

      setError(
        err?.message ||
        "Failed to submit threat input."
      );

    } finally {

      setLoading(false);

    }
  };

  return (
    <section className="panel">

      <h2>Threat Intelligence</h2>

      <p>
        Submit a threat-intelligence indicator
        for real-time Detection, Risk and Alert
        processing.
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns:
            "repeat(auto-fit,minmax(220px,1fr))",
          gap: "12px",
          marginTop: "16px"
        }}
      >

        <div>
          <label>Indicator Type</label>

          <select
            value={indicatorType}
            onChange={(e) =>
              setIndicatorType(e.target.value)
            }
            style={{
              width: "100%",
              padding: "10px",
              marginTop: "6px"
            }}
          >
            <option value="WALLET_ADDRESS">
              WALLET_ADDRESS
            </option>

            <option value="TX_HASH">
              TX_HASH
            </option>

            <option value="IP_ADDRESS">
              IP_ADDRESS
            </option>

            <option value="DOMAIN">
              DOMAIN
            </option>

            <option value="URL">
              URL
            </option>

            <option value="EMAIL">
              EMAIL
            </option>

          </select>
        </div>

        <div>
          <label>Indicator</label>

          <input
            value={indicator}
            onChange={(e) =>
              setIndicator(e.target.value)
            }
            placeholder="Enter indicator"
            style={{
              width: "100%",
              padding: "10px",
              marginTop: "6px"
            }}
          />
        </div>

        <div>
          <label>Source</label>

          <input
            value={source}
            onChange={(e) =>
              setSource(e.target.value)
            }
            style={{
              width: "100%",
              padding: "10px",
              marginTop: "6px"
            }}
          />
        </div>

        <div>
          <label>Network</label>

          <select
            value={network}
            onChange={(e) =>
              setNetwork(e.target.value)
            }
            style={{
              width: "100%",
              padding: "10px",
              marginTop: "6px"
            }}
          >
            <option value="Ethereum">
              Ethereum
            </option>

            <option value="Bitcoin">
              Bitcoin
            </option>

            <option value="Solana">
              Solana
            </option>

            <option value="Unknown">
              Unknown
            </option>

          </select>
        </div>

        <div>
          <label>Confidence</label>

          <select
            value={confidence}
            onChange={(e) =>
              setConfidence(e.target.value)
            }
            style={{
              width: "100%",
              padding: "10px",
              marginTop: "6px"
            }}
          >
            <option value="LOW">LOW</option>
            <option value="MEDIUM">MEDIUM</option>
            <option value="HIGH">HIGH</option>
          </select>
        </div>

        <div>
          <label>Severity</label>

          <select
            value={severity}
            onChange={(e) =>
              setSeverity(e.target.value)
            }
            style={{
              width: "100%",
              padding: "10px",
              marginTop: "6px"
            }}
          >
            <option value="LOW">LOW</option>
            <option value="MEDIUM">MEDIUM</option>
            <option value="HIGH">HIGH</option>
            <option value="CRITICAL">CRITICAL</option>
          </select>
        </div>

      </div>

      <button
        onClick={submitThreatInput}
        disabled={loading}
        style={{
          marginTop: "18px",
          padding: "10px 18px",
          cursor: loading
            ? "not-allowed"
            : "pointer"
        }}
      >
        {loading
          ? "Processing..."
          : "Submit Threat Indicator"}
      </button>

      {error && (
        <div
          style={{
            marginTop: "16px",
            padding: "12px"
          }}
        >
          {error}
        </div>
      )}

      {result && (
        <div style={{ marginTop: "20px" }}>

          <h3>Processing Result</h3>

          <div
            style={{
              display: "grid",
              gridTemplateColumns:
                "repeat(auto-fit,minmax(180px,1fr))",
              gap: "10px",
              marginTop: "12px"
            }}
          >

            <div className="panel">
              <b>Detection</b>
              <div>
                {result?.processing?.detection?.type ||
                  "—"}
              </div>
            </div>

            <div className="panel">
              <b>Risk Score</b>
              <div>
                {result?.processing?.risk?.risk_score ??
                  "—"}
              </div>
            </div>

            <div className="panel">
              <b>Risk Level</b>
              <div>
                {result?.processing?.risk?.risk_level ||
                  "—"}
              </div>
            </div>

            <div className="panel">
              <b>Alert</b>
              <div>
                {result?.processing?.alert?.alert_id ||
                  "No Alert"}
              </div>
            </div>

          </div>

          <details style={{ marginTop: "16px" }}>

            <summary>
              View Full Processing Response
            </summary>

            <pre
              style={{
                marginTop: "10px",
                whiteSpace: "pre-wrap",
                overflowX: "auto"
              }}
            >
              {JSON.stringify(
                result,
                null,
                2
              )}
            </pre>

          </details>

        </div>
      )}

    </section>
  );
}

function FundFlow() {

  const [network, setNetwork] =
    useState<"bitcoin" | "ethereum">("bitcoin");

  const [a, setA] =
    useState("");

  const [r, setR] =
    useState<any>(null);

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState("");


  /* TRACE FLOW */

  const traceFlow = async () => {

    const address =
      a.trim();

    if (!address) {

      setError(
        network === "bitcoin"
          ? "Please enter a Bitcoin wallet address."
          : "Please enter an Ethereum wallet address."
      );

      return;
    }

    setLoading(true);
    setError("");
    setR(null);

    try {

      const response =
        await fetch(
          `${API}/api/fundflow/${encodeURIComponent(
            address
          )}?network=${network}&hops=2`
        );

      const data =
        await response.json();

      if (!response.ok) {

        throw new Error(
          data.detail ||
          "Fund-flow investigation failed"
        );

      }

      setR(data);

    } catch (e: any) {

      setError(
        e.message ||
        "Fund-flow investigation failed"
      );

    } finally {

      setLoading(false);

    }

  };


  /* BITCOIN AMOUNT */

  const btc = (
    sats: number
  ) => {

    return (
      (
        (Number(sats) || 0) /
        100000000
      ).toFixed(8) +
      " BTC"
    );

  };


  /* ETH AMOUNT */

  const eth = (
    value: any
  ) => {

    if (
      value === undefined ||
      value === null ||
      value === ""
    ) {

      return "0 ETH";

    }

    const numberValue =
      Number(value);

    if (
      Number.isFinite(
        numberValue
      )
    ) {

      return (
        numberValue.toLocaleString(
          undefined,
          {
            maximumFractionDigits: 18
          }
        ) +
        " ETH"
      );

    }

    return (
      String(value) +
      " ETH"
    );

  };


  /* GET FLOW EDGES */

  const getFlowEdges = (): any[] => {

    if (
      Array.isArray(r?.edges) &&
      r.edges.length > 0
    ) {

      return r.edges;

    }

    if (
      Array.isArray(r?.edges_data) &&
      r.edges_data.length > 0
    ) {

      return r.edges_data;

    }

    return [];

  };


  /* EDGE COUNT */

  const getEdgeCount = () => {

    const edges =
      getFlowEdges();

    const backendCount =
      Number(
        r?.edge_count || 0
      );

    return Math.max(
      backendCount,
      edges.length
    );

  };


  /* TRANSACTION COUNT */

  const getTransactionCount = () => {

    const edges =
      getFlowEdges();

    const backendCount =
      Number(
        r?.transactions_scanned ||
        r?.transactions ||
        0
      );

    return Math.max(
      backendCount,
      edges.length
    );

  };


  /* SHORT ADDRESS */

  const shortAddress = (
    value: any
  ) => {

    if (!value) {

      return "Unknown";

    }

    const text =
      String(value);

    if (
      text.length > 20
    ) {

      return (
        text.slice(0, 12) +
        "..." +
        text.slice(-6)
      );

    }

    return text;

  };


  /* SHORT TRANSACTION HASH */

  const shortHash = (
    value: any
  ) => {

    if (!value) {

      return "Unknown";

    }

    const text =
      String(value);

    if (
      text.length > 20
    ) {

      return (
        text.slice(0, 16) +
        "..."
      );

    }

    return text;

  };


  /* TRANSACTION HASH */

  const getTxHash = (
    edge: any
  ) => {

    return (
      edge?.transaction_hash ||
      edge?.txid ||
      edge?.hash ||
      ""
    );

  };


  /* TOKEN DETECTION */

  const isTokenTransfer = (
    edge: any
  ) => {

    return (
      edge?.transfer_type === "token" ||
      edge?.type === "token" ||
      edge?.asset === "ERC-20" ||
      !!edge?.token_address ||
      !!edge?.contract_address
    );

  };


  /* NATIVE TRANSFER DETECTION */

  const isNativeTransfer = (
    edge: any
  ) => {

    return (
      edge?.transfer_type === "native" ||
      edge?.type === "native" ||
      edge?.asset === "ETH" ||
      edge?.token_symbol === "ETH" ||
      edge?.value_eth !== undefined
    );

  };


  /* TOKEN LABEL */

  const getTokenLabel = (
    edge: any
  ) => {

    const symbol =
      edge?.token_symbol;

    const name =
      edge?.token_name;

    if (
      symbol &&
      String(symbol).toUpperCase() !== "UNKNOWN"
    ) {

      return String(symbol);

    }

    if (
      name &&
      String(name).toUpperCase() !== "UNKNOWN"
    ) {

      return String(name);

    }

    return "ERC-20";

  };


  /* TOKEN CONTRACT */

  const getTokenContract = (
    edge: any
  ) => {

    return (
      edge?.token_address ||
      edge?.contract_address ||
      ""
    );

  };


  /* ERC-20 AMOUNT */

  const formatTokenAmount = (
    edge: any
  ) => {

    const label =
      getTokenLabel(edge);

    const rawValue =
      edge?.value_raw ??
      edge?.value_token ??
      edge?.value ??
      null;

    if (
      rawValue === null ||
      rawValue === undefined ||
      rawValue === ""
    ) {

      return (
        "ERC-20 " +
        label
      );

    }


    const decimalsRaw =
      edge?.decimals;

    const decimals =
      Number(decimalsRaw);


    /*
     * If token metadata is unknown
     * and decimals are 0, do not
     * pretend that a huge raw value
     * is a normal token amount.
     */

    const tokenIsUnknown =
      label === "ERC-20";


    if (
      !tokenIsUnknown &&
      Number.isInteger(decimals) &&
      decimals >= 0 &&
      decimals <= 36
    ) {

      const rawNumber =
        Number(rawValue);

      if (
        Number.isFinite(rawNumber)
      ) {

        const divisor =
          Math.pow(
            10,
            decimals
          );

        const tokenAmount =
          rawNumber / divisor;

        if (
          Number.isFinite(tokenAmount)
        ) {

          return (
            tokenAmount.toLocaleString(
              undefined,
              {
                maximumFractionDigits: 8
              }
            ) +
            " " +
            label
          );

        }

      }

    }


    /*
     * Metadata is not reliable.
     * Show the raw blockchain value
     * explicitly instead of mislabelling it.
     */

    return (
      "Raw: " +
      String(rawValue) +
      " " +
      label
    );

  };


  /* AMOUNT */

  const formatAmount = (
    edge: any
  ) => {

    /* BITCOIN */

    if (
      network === "bitcoin"
    ) {

      if (
        edge?.value_sats !== undefined &&
        edge?.value_sats !== null
      ) {

        return btc(
          Number(
            edge.value_sats
          )
        );

      }

      if (
        edge?.value_btc !== undefined &&
        edge?.value_btc !== null
      ) {

        const value =
          Number(
            edge.value_btc
          );

        if (
          Number.isFinite(value)
        ) {

          return (
            value.toLocaleString(
              undefined,
              {
                maximumFractionDigits: 8
              }
            ) +
            " BTC"
          );

        }

      }

      return "0 BTC";

    }


    /* ETHEREUM */

    /*
     * Check token first.
     * This prevents ERC-20 transfers
     * from being displayed as ETH.
     */

    if (
      isTokenTransfer(edge)
    ) {

      return formatTokenAmount(
        edge
      );

    }


    /* NATIVE ETH */

    if (
      isNativeTransfer(edge)
    ) {

      if (
        edge?.value_eth !== undefined &&
        edge?.value_eth !== null
      ) {

        return eth(
          edge.value_eth
        );

      }

      return "0 ETH";

    }


    return "TRANSFER";

  };


  /* EDGE TYPE */

  const getEdgeType = (
    edge: any
  ) => {

    if (
      isTokenTransfer(edge)
    ) {

      return (
        "TOKEN • " +
        getTokenLabel(edge)
      );

    }


    if (
      isNativeTransfer(edge)
    ) {

      return (
        "NATIVE • " +
        (
          edge?.asset ||
          "ETH"
        )
      );

    }


    const type =
      edge?.type ||
      edge?.transfer_type ||
      edge?.transaction_type ||
      edge?.asset_type ||
      edge?.category;

    if (type) {

      const normalized =
        String(type).toUpperCase();

      if (
        normalized !== "UNKNOWN"
      ) {

        return normalized;

      }

    }

    return "TRANSFER";

  };


  /* ETHEREUM BLOCKSCOUT URL */

  const getExplorerUrl = (
    txHash: string
  ) => {

    if (
      network !== "ethereum" ||
      !txHash
    ) {

      return "";

    }

    return (
      `https://eth.blockscout.com/tx/${txHash}`
    );

  };


  /* FLOW EDGES */

  const flowEdges =
    getFlowEdges();


  return (

    <section className="panel">

      <h2>

        {network === "bitcoin"
          ? "Bitcoin Fund Flow Investigation"
          : "Ethereum Fund Flow Investigation"}

      </h2>


      <p>

        Trace wallet relationships
        and transaction flows
        using live blockchain data.

      </p>


      {/* NETWORK */}

      <div
        style={{
          display: "flex",
          gap: "8px",
          marginBottom: "14px"
        }}
      >

        <button

          className={
            network === "bitcoin"
              ? "primary"
              : "nav"
          }

          onClick={() => {

            setNetwork("bitcoin");
            setA("");
            setR(null);
            setError("");

          }}

        >

          Bitcoin

        </button>


        <button

          className={
            network === "ethereum"
              ? "primary"
              : "nav"
          }

          onClick={() => {

            setNetwork("ethereum");
            setA("");
            setR(null);
            setError("");

          }}

        >

          Ethereum

        </button>

      </div>


      {/* SEARCH */}

      <div className="searchBox">

        <input

          value={a}

          onChange={(e) =>
            setA(
              e.target.value
            )
          }

          onKeyDown={(e) => {

            if (
              e.key === "Enter"
            ) {

              traceFlow();

            }

          }}

          placeholder={
            network === "bitcoin"
              ? "Enter Bitcoin wallet address"
              : "Enter Ethereum wallet address"
          }

        />


        <button

          className="primary"

          onClick={traceFlow}

          disabled={loading}

        >

          {loading
            ? "Tracing..."
            : "Trace Flow"}

        </button>

      </div>


      {/* ERROR */}

      {error && (

        <div className="empty">

          {error}

        </div>

      )}


      {/* RESULTS */}

      {r && (

        <>

          {/* SUMMARY */}

          <div className="cards">

            <Card

              title="NETWORK"

              value={
                r.network ||
                (
                  network === "bitcoin"
                    ? "Bitcoin"
                    : "Ethereum"
                )
              }

              sub="Blockchain"

            />


            <Card

              title="WALLETS"

              value={String(
                r.wallet_count ??
                r.nodes?.length ??
                0
              )}

              sub="Wallets identified"

            />


            <Card

              title="EDGES"

              value={String(
                getEdgeCount()
              )}

              sub="Fund-flow relationships"

            />


            <Card

              title="TRANSACTIONS"

              value={String(
                getTransactionCount()
              )}

              sub="Transactions scanned"

            />

          </div>


          {/* INVESTIGATION SUMMARY */}

          <section className="panel">

            <h2>
              Investigation Summary
            </h2>


            <div className="row">

              <b>
                Root Wallet
              </b>

              <span
                style={{
                  fontFamily: "monospace",
                  wordBreak: "break-all"
                }}
              >

                {r.root ||
                  r.root_wallet ||
                  a}

              </span>

            </div>


            <div className="row">

              <b>
                Status
              </b>

              <span className="liveDot">

                ● {r.status || "LIVE"}

              </span>

            </div>


            <div className="row">

              <b>
                Hops Requested
              </b>

              <span>

                {r.hops_requested ?? "—"}

              </span>

            </div>


            <div className="row">

              <b>
                Hops Traced
              </b>

              <span>

                {r.hops_traced ?? "—"}

              </span>

            </div>


            <div className="row">

              <b>
                Data Source
              </b>

              <span>

                {r.source ||
                  "Blockchain API"}

              </span>

            </div>

          </section>


          {/* GRAPH */}

          <FundFlowGraph

            nodes={
              r.nodes || []
            }

            edges={
              Array.isArray(r.edges)
                ? r.edges
                : []
            }

            edges_data={
              Array.isArray(r.edges_data)
                ? r.edges_data
                : []
            }

          />


          {/* TRANSACTIONS */}

          <section className="panel">

            <h2>
              Fund Flow Transactions
            </h2>


            {flowEdges.length > 0 ? (

              <div className="table">

                <div className="thead">

                  <span>
                    Source
                  </span>

                  <span>
                    Target
                  </span>

                  <span>
                    Amount
                  </span>

                  <span>
                    Type
                  </span>

                  <span>
                    TXID
                  </span>

                  <span>
                    Hop
                  </span>

                </div>


                {flowEdges
                  .slice(0, 50)
                  .map(
                    (
                      edge: any,
                      i: number
                    ) => {

                      const txHash =
                        getTxHash(edge);

                      const explorerUrl =
                        getExplorerUrl(
                          txHash
                        );


                      return (

                        <div

                          className="tr"

                          key={
                            `${txHash || i}-${i}`
                          }

                        >

                          {/* SOURCE */}

                          <span

                            title={
                              edge.source ||
                              ""
                            }

                            style={{
                              fontFamily:
                                "monospace"
                            }}

                          >

                            {shortAddress(
                              edge.source
                            )}

                          </span>


                          {/* TARGET */}

                          <span

                            title={
                              edge.target ||
                              ""
                            }

                            style={{
                              fontFamily:
                                "monospace"
                            }}

                          >

                            {shortAddress(
                              edge.target
                            )}

                          </span>


                          {/* AMOUNT */}

                          <span

                            title={
                              isTokenTransfer(
                                edge
                              )
                                ? (
                                    getTokenContract(
                                      edge
                                    )
                                      ? `Token Contract: ${getTokenContract(edge)}`
                                      : "ERC-20 token contract unavailable"
                                  )
                                : ""
                            }

                          >

                            {formatAmount(
                              edge
                            )}

                          </span>


                          {/* TYPE */}

                          <span

                            className={
                              String(
                                edge.direction ||
                                ""
                              ).toUpperCase() ===
                              "INCOMING"
                                ? "up"
                                : String(
                                    edge.direction ||
                                    ""
                                  ).toUpperCase() ===
                                  "OUTGOING"
                                ? "down"
                                : ""
                            }

                          >

                            {getEdgeType(
                              edge
                            )}

                          </span>


                          {/* TXID */}

                          <span

                            title={
                              txHash ||
                              "No transaction hash"
                            }

                            style={{
                              fontFamily:
                                "monospace",
                              wordBreak:
                                "break-all"
                            }}

                          >

                            {txHash ? (

                              explorerUrl ? (

                                <a

                                  href={
                                    explorerUrl
                                  }

                                  target="_blank"

                                  rel="noopener noreferrer"

                                >

                                  {shortHash(
                                    txHash
                                  )}

                                </a>

                              ) : (

                                shortHash(
                                  txHash
                                )

                              )

                            ) : (

                              "Unknown"

                            )}

                          </span>


                          {/* HOP */}

                          <span>

                            {edge.hop ?? "—"}

                          </span>

                        </div>

                      );

                    }
                  )}

              </div>

            ) : (

              <div className="empty">

                No fund-flow
                transactions found.

              </div>

            )}

          </section>


          {/* WALLET NETWORK */}

          <section className="panel">

            <h2>
              Wallet Network
            </h2>


            {Array.isArray(r.nodes) &&
            r.nodes.length > 0 ? (

              <div className="table">

                <div className="thead">

                  <span>
                    Wallet
                  </span>

                  <span>
                    Type
                  </span>

                  <span>
                    Hop
                  </span>

                </div>


                {r.nodes
                  .slice(0, 50)
                  .map(
                    (
                      node: any,
                      i: number
                    ) => (

                      <div

                        className="tr"

                        key={
                          node.id || i
                        }

                      >

                        <span

                          title={
                            node.id || ""
                          }

                          style={{
                            fontFamily:
                              "monospace"
                          }}

                        >

                          {node.label ||
                            shortAddress(
                              node.id
                            )}

                        </span>


                        <span>

                          {node.type ||
                            "wallet"}

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

  // =====================================================
  // BITCOIN STATE
  // =====================================================

  const [blocks,setBlocks]=useState<any[]>([]);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");

  const [selectedBlock,setSelectedBlock]=useState<any>(null);
  const [detailsLoading,setDetailsLoading]=useState(false);
  const [detailsError,setDetailsError]=useState("");


  // =====================================================
  // ETHEREUM STATE
  // =====================================================

  const [ethereumBlocks,setEthereumBlocks]=useState<any[]>([]);
  const [ethereumLoading,setEthereumLoading]=useState(true);
  const [ethereumError,setEthereumError]=useState("");

  const [
    selectedEthereumBlock,
    setSelectedEthereumBlock
  ]=useState<any>(null);

  const [
    ethereumDetailsLoading,
    setEthereumDetailsLoading
  ]=useState(false);

  const [
    ethereumDetailsError,
    setEthereumDetailsError
  ]=useState("");


  // =====================================================
  // BITCOIN LIVE BLOCKS
  // AUTO REFRESH EVERY 10 SECONDS
  // =====================================================

  useEffect(()=>{

    let mounted=true;

    const loadBitcoinBlocks=async()=>{

      try{

        const response=await fetch(
          `${API}/api/blockchain/bitcoin/blocks`
        );

        const data=await response.json();

        if(!response.ok){

          throw new Error(
            data.detail ||
            "Bitcoin Blockchain API unavailable"
          );

        }

        if(!mounted){
          return;
        }

        setBlocks(
          data.blocks || []
        );

        setError("");
        setLoading(false);

      }catch(e:any){

        if(!mounted){
          return;
        }

        setError(
          e.message ||
          "Bitcoin Blockchain API unavailable"
        );

        setLoading(false);

      }

    };

    // Initial load
    loadBitcoinBlocks();

    // Refresh every 10 seconds
    const interval=setInterval(
      loadBitcoinBlocks,
      10000
    );

    return ()=>{

      mounted=false;
      clearInterval(interval);

    };

  },[]);


  // =====================================================
  // ETHEREUM LIVE BLOCKS
  // AUTO REFRESH EVERY 10 SECONDS
  // =====================================================

  useEffect(()=>{

    let mounted=true;

    const loadEthereumBlocks=async()=>{

      try{

        const response=await fetch(
          `${API}/api/blockchain/ethereum/blocks`
        );

        const data=await response.json();

        if(!response.ok){

          throw new Error(
            data.detail ||
            "Ethereum Blockchain API unavailable"
          );

        }

        if(!mounted){
          return;
        }

        setEthereumBlocks(
          data.blocks || []
        );

        setEthereumError("");
        setEthereumLoading(false);

      }catch(e:any){

        if(!mounted){
          return;
        }

        setEthereumError(
          e.message ||
          "Ethereum Blockchain API unavailable"
        );

        setEthereumLoading(false);

      }

    };

    // Initial load
    loadEthereumBlocks();

    // Refresh every 10 seconds
    const interval=setInterval(
      loadEthereumBlocks,
      10000
    );

    return ()=>{

      mounted=false;
      clearInterval(interval);

    };

  },[]);


  // =====================================================
  // BITCOIN BLOCK DETAILS
  // =====================================================

  const openBlockDetails=async(
    block:any
  )=>{

    if(!block?.hash){
      return;
    }

    setSelectedBlock(null);
    setDetailsError("");
    setDetailsLoading(true);

    try{

      const response=await fetch(
        `${API}/api/blockchain/bitcoin/block/${encodeURIComponent(block.hash)}`
      );

      const data=await response.json();

      if(!response.ok){

        throw new Error(
          data.detail ||
          "Bitcoin block details unavailable"
        );

      }

      setSelectedBlock(
        data.block || null
      );

    }catch(e:any){

      setDetailsError(
        e.message ||
        "Bitcoin block details unavailable"
      );

    }finally{

      setDetailsLoading(false);

    }

  };


  // =====================================================
  // ETHEREUM BLOCK DETAILS
  // =====================================================

  const openEthereumBlockDetails=async(
    block:any
  )=>{

    if(
      block?.height === undefined ||
      block?.height === null
    ){
      return;
    }

    setSelectedEthereumBlock(null);
    setEthereumDetailsError("");
    setEthereumDetailsLoading(true);

    try{

      const response=await fetch(
        `${API}/api/blockchain/ethereum/block/${encodeURIComponent(block.height)}`
      );

      const data=await response.json();

      if(!response.ok){

        throw new Error(
          data.detail ||
          "Ethereum block details unavailable"
        );

      }

      setSelectedEthereumBlock(
        data.block || null
      );

    }catch(e:any){

      setEthereumDetailsError(
        e.message ||
        "Ethereum block details unavailable"
      );

    }finally{

      setEthereumDetailsLoading(false);

    }

  };


  // =====================================================
  // TIME FORMAT
  // =====================================================

  const formatTime=(timestamp:any)=>{

    if(
      timestamp === undefined ||
      timestamp === null
    ){
      return "—";
    }

    return new Date(
      Number(timestamp)*1000
    ).toLocaleString();

  };


  // =====================================================
  // FORMAT ETHEREUM BASE FEE
  // =====================================================

  const formatBaseFee=(value:any)=>{

    if(
      value === undefined ||
      value === null
    ){
      return "—";
    }

    return Number(
      value
    ).toLocaleString();

  };


  // =====================================================
  // UI
  // =====================================================

  return(

    <section className="panel">

      <h2>
        Blockchain Intelligence
      </h2>

      <p>
        Multi-chain • Live blockchain data
      </p>

      {/* =================================================
          NETWORK OVERVIEW
      ================================================= */}

      <section className="panel">

        <h2>
          Network Overview
        </h2>

        <p>
          Real-time blockchain network status
        </p>

        <div className="cards">

          <Card
            title="₿ BITCOIN"
            value={
              blocks.length > 0 &&
              blocks[0]?.height != null
                ? String(blocks[0].height)
                : "—"
            }
            sub="Latest block • LIVE"
          />

          <Card
            title="Ξ ETHEREUM"
            value={
              ethereumBlocks.length > 0 &&
              ethereumBlocks[0]?.height != null
                ? String(ethereumBlocks[0].height)
                : "—"
            }
            sub="Latest block • LIVE"
          />

          <Card
            title="BTC TX ACTIVITY"
            value={
              blocks.length > 0
                ? String(blocks[0]?.n_tx ?? 0)
                : "—"
            }
            sub="Transactions in latest block"
          />

          <Card
            title="ETH TX ACTIVITY"
            value={
              ethereumBlocks.length > 0
                ? String(ethereumBlocks[0]?.tx_count ?? 0)
                : "—"
            }
            sub="Transactions in latest block"
          />

        </div>

      </section>


      {/* =================================================
          BITCOIN
      ================================================= */}

      <section className="panel">

        <h2>
          Bitcoin Blockchain Intelligence
        </h2>

        <p>
          LIVE blockchain data from Bitcoin network
        </p>


        {loading && (

          <div className="empty">
            Loading live Bitcoin blocks...
          </div>

        )}


        {error && (

          <div className="empty">
            {error}
          </div>

        )}


        {!loading && !error && (

          <div className="table">

            <div className="thead">

              <span>
                Height
              </span>

              <span>
                Block Hash
              </span>

              <span>
                Transactions
              </span>

              <span>
                Size
              </span>

              <span>
                Weight
              </span>

              <span>
                Status
              </span>

            </div>


            {blocks.map(
              (b,i)=>(

                <div
                  className="tr"
                  key={b.hash || i}
                  onClick={()=>
                    openBlockDetails(b)
                  }
                  style={{
                    cursor:
                      b.hash
                        ? "pointer"
                        : "default"
                  }}
                  title={
                    b.hash
                      ? "Click to view Bitcoin block details"
                      : ""
                  }
                >

                  <b>
                    {b.height ?? "—"}
                  </b>


                  <span
                    title={b.hash || ""}
                    style={{
                      fontFamily:"monospace"
                    }}
                  >

                    {b.hash
                      ? b.hash.slice(0,18)+"..."
                      : "—"}

                  </span>


                  <span>
                    {b.n_tx ?? 0}
                  </span>


                  <span>

                    {b.size
                      ? b.size.toLocaleString()
                      : "—"}

                  </span>


                  <span>

                    {b.weight
                      ? b.weight.toLocaleString()
                      : "—"}

                  </span>


                  <span className="liveDot">
                    ● LIVE
                  </span>

                </div>

              )
            )}

          </div>

        )}

      </section>


      {/* =================================================
          BITCOIN DETAILS
      ================================================= */}

      {detailsLoading && (

        <section className="panel">

          <h2>
            Bitcoin Block Details
          </h2>

          <div className="empty">
            Loading block details...
          </div>

        </section>

      )}


      {detailsError && (

        <section className="panel">

          <h2>
            Bitcoin Block Details
          </h2>

          <div className="empty">
            {detailsError}
          </div>

        </section>

      )}


      {selectedBlock && (

        <section className="panel">

          <div
            style={{
              display:"flex",
              justifyContent:"space-between",
              alignItems:"center",
              gap:"12px"
            }}
          >

            <div>

              <h2>
                Bitcoin Block Details
              </h2>

              <p>
                Live Bitcoin block information
              </p>

            </div>


            <button
              className="primary"
              onClick={()=>
                setSelectedBlock(null)
              }
            >
              Close
            </button>

          </div>


          <div className="cards">

            <Card
              title="HEIGHT"
              value={
                String(
                  selectedBlock.height ?? "—"
                )
              }
              sub="Block height"
            />


            <Card
              title="TRANSACTIONS"
              value={
                String(
                  selectedBlock.tx_count ?? 0
                )
              }
              sub="Transactions in block"
            />


            <Card
              title="SIZE"
              value={
                selectedBlock.size
                  ? selectedBlock.size.toLocaleString()
                  : "—"
              }
              sub="Bytes"
            />


            <Card
              title="WEIGHT"
              value={
                selectedBlock.weight
                  ? selectedBlock.weight.toLocaleString()
                  : "—"
              }
              sub="Block weight"
            />

          </div>


          <section className="panel">

            <h2>
              Block Information
            </h2>


            <div className="row">
              <b>Full Block Hash</b>

              <span
                style={{
                  fontFamily:"monospace",
                  wordBreak:"break-all"
                }}
              >
                {selectedBlock.hash || "—"}
              </span>
            </div>


            <div className="row">
              <b>Timestamp</b>

              <span>
                {formatTime(
                  selectedBlock.timestamp
                )}
              </span>
            </div>


            <div className="row">
              <b>Version</b>

              <span>
                {selectedBlock.version ?? "—"}
              </span>
            </div>


            <div className="row">
              <b>Merkle Root</b>

              <span
                style={{
                  fontFamily:"monospace",
                  wordBreak:"break-all"
                }}
              >
                {selectedBlock.merkle_root || "—"}
              </span>

            </div>


            <div className="row">
              <b>Previous Block Hash</b>

              <span
                style={{
                  fontFamily:"monospace",
                  wordBreak:"break-all"
                }}
              >
                {selectedBlock.previous_block_hash || "—"}
              </span>

            </div>


            <div className="row">
              <b>Nonce</b>

              <span>
                {selectedBlock.nonce ?? "—"}
              </span>
            </div>


            <div className="row">
              <b>Bits</b>

              <span>
                {selectedBlock.bits ?? "—"}
              </span>
            </div>


            <div className="row">
              <b>Difficulty</b>

              <span>
                {selectedBlock.difficulty != null
                  ? Number(
                      selectedBlock.difficulty
                    ).toLocaleString()
                  : "—"}
              </span>
            </div>


            <div className="row">
              <b>Network</b>

              <span>
                Bitcoin
              </span>
            </div>


            <div className="row">
              <b>Status</b>

              <span className="liveDot">
                ● LIVE
              </span>
            </div>

          </section>

        </section>

      )}


      {/* =================================================
          ETHEREUM
      ================================================= */}

      <section className="panel">

        <h2>
          Ethereum Blockchain Intelligence
        </h2>

        <p>
          LIVE blockchain data from Ethereum Mainnet
        </p>


        {ethereumLoading && (

          <div className="empty">
            Loading live Ethereum blocks...
          </div>

        )}


        {ethereumError && (

          <div className="empty">
            {ethereumError}
          </div>

        )}


        {!ethereumLoading &&
         !ethereumError && (

          <div className="table">

            <div className="thead">

              <span>
                Block
              </span>

              <span>
                Block Hash
              </span>

              <span>
                Transactions
              </span>

              <span>
                Gas Used
              </span>

              <span>
                Gas Limit
              </span>

              <span>
                Base Fee
              </span>

            </div>


            {ethereumBlocks.map(
              (b,i)=>(

                <div
                  className="tr"
                  key={b.hash || i}
                  onClick={()=>
                    openEthereumBlockDetails(b)
                  }
                  style={{
                    cursor:"pointer"
                  }}
                  title="Click to view Ethereum block details"
                >

                  <b>
                    {b.height ?? "—"}
                  </b>


                  <span
                    title={b.hash || ""}
                    style={{
                      fontFamily:"monospace"
                    }}
                  >

                    {b.hash
                      ? b.hash.slice(0,18)+"..."
                      : "—"}

                  </span>


                  <span>
                    {b.tx_count ?? 0}
                  </span>


                  <span>
                    {b.gas_used != null
                      ? b.gas_used.toLocaleString()
                      : "—"}
                  </span>


                  <span>
                    {b.gas_limit != null
                      ? b.gas_limit.toLocaleString()
                      : "—"}
                  </span>


                  <span>
                    {formatBaseFee(
                      b.base_fee_per_gas
                    )}
                  </span>

                </div>

              )
            )}

          </div>

        )}

      </section>


      {/* =================================================
          ETHEREUM DETAILS
      ================================================= */}

      {ethereumDetailsLoading && (

        <section className="panel">

          <h2>
            Ethereum Block Details
          </h2>

          <div className="empty">
            Loading Ethereum block details...
          </div>

        </section>

      )}


      {ethereumDetailsError && (

        <section className="panel">

          <h2>
            Ethereum Block Details
          </h2>

          <div className="empty">
            {ethereumDetailsError}
          </div>

        </section>

      )}


      {selectedEthereumBlock && (

  <section className="panel">

    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: "12px"
      }}
    >

      <div>

        <h2>
          Ethereum Block Details
        </h2>

        <p>
          Live Ethereum Mainnet block information
        </p>

      </div>

      <button
        className="primary"
        onClick={() => setSelectedEthereumBlock(null)}
      >
        Close
      </button>

    </div>


    <div className="cards">

      <Card
        title="BLOCK"
        value={String(selectedEthereumBlock.height ?? "—")}
        sub="Ethereum block number"
      />

      <Card
        title="TRANSACTIONS"
        value={String(selectedEthereumBlock.tx_count ?? 0)}
        sub="Transactions in block"
      />

      <Card
        title="GAS USED"
        value={
          selectedEthereumBlock.gas_used != null
            ? Number(selectedEthereumBlock.gas_used).toLocaleString()
            : "—"
        }
        sub="Gas used"
      />

      <Card
        title="GAS LIMIT"
        value={
          selectedEthereumBlock.gas_limit != null
            ? Number(selectedEthereumBlock.gas_limit).toLocaleString()
            : "—"
        }
        sub="Block gas limit"
      />

    </div>


    {/* =========================================
        ETHEREUM BLOCK INFORMATION
       ========================================= */}

    <section className="panel">

      <h2>
        Ethereum Block Information
      </h2>

      <div className="row">
        <b>Block Hash</b>
        <span
          style={{
            fontFamily: "monospace",
            wordBreak: "break-all"
          }}
        >
          {selectedEthereumBlock.hash || "—"}
        </span>
      </div>

      <div className="row">
        <b>Parent Hash</b>
        <span
          style={{
            fontFamily: "monospace",
            wordBreak: "break-all"
          }}
        >
          {selectedEthereumBlock.parent_hash || "—"}
        </span>
      </div>

      <div className="row">
        <b>State Root</b>
        <span
          style={{
            fontFamily: "monospace",
            wordBreak: "break-all"
          }}
        >
          {selectedEthereumBlock.state_root || "—"}
        </span>
      </div>

      <div className="row">
        <b>Transactions Root</b>
        <span
          style={{
            fontFamily: "monospace",
            wordBreak: "break-all"
          }}
        >
          {selectedEthereumBlock.transactions_root || "—"}
        </span>
      </div>

      <div className="row">
        <b>Receipts Root</b>
        <span
          style={{
            fontFamily: "monospace",
            wordBreak: "break-all"
          }}
        >
          {selectedEthereumBlock.receipts_root || "—"}
        </span>
      </div>

      <div className="row">
        <b>Timestamp</b>
        <span>
          {selectedEthereumBlock.timestamp
            ? new Date(
                Number(selectedEthereumBlock.timestamp) * 1000
              ).toLocaleString()
            : "—"}
        </span>
      </div>

      <div className="row">
        <b>Base Fee Per Gas</b>
        <span>
          {formatBaseFee(selectedEthereumBlock.base_fee_per_gas)}
        </span>
      </div>

      <div className="row">
        <b>Status</b>
        <span className="liveDot">
          ● LIVE
        </span>
      </div>

    </section>


    {/* =========================================
        ETHEREUM BLOCK TRANSACTIONS
       ========================================= */}

    <section className="panel">

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "12px",
          marginBottom: "12px"
        }}
      >

        <div>

          <h2>
            Block Transactions
          </h2>

          <p
            style={{
              margin: 0,
              color: "#71818c",
              fontSize: "11px"
            }}
          >
            Real Ethereum transaction hashes
            contained in this block.
          </p>

        </div>

        <span className="liveDot">
          ● LIVE DATA
        </span>

      </div>


      <div
        id="ethereum-block-transactions"
        className="table"
      >

        <div
          className="thead"
          style={{
            gridTemplateColumns: "70px 1fr"
          }}
        >

          <span>#</span>

          <span>
            Transaction Hash
          </span>

        </div>


                {Array.isArray(selectedEthereumBlock.transactions) &&
        selectedEthereumBlock.transactions.length > 0 ? (

          selectedEthereumBlock.transactions.map(
            (txHash: string, index: number) => (
              <div
                className="tr"
                key={`${txHash}-${index}`}
                style={{
                  gridTemplateColumns: "70px 1fr"
                }}
              >
                <span>
                  {index + 1}
                </span>

                <span
                  style={{
                    fontFamily: "monospace",
                    wordBreak: "break-all"
                  }}
                >
                  {txHash}
                </span>
              </div>
            )
          )

        ) : (

          <div className="empty">
            No transaction hashes available
            for this block.
          </div>

               )}

      </div>

    </section>

  </section>

)}

</section>

);
}
