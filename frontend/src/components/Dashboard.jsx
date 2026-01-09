import { useEffect, useState, useRef } from 'react';
import { socket, api } from '../api';
import { Link } from 'react-router-dom';
import LiveChart from './LiveChart';
import TradeLog from './TradeLog';
import StockChart from './StockChart'; // NEW
import AgentDetailModal from './AgentDetailModal'; // NEW
import NewsFeed from './NewsFeed'; // NEW

const Dashboard = () => {
    const [priceData, setPriceData] = useState([]);
    const [agents, setAgents] = useState([]);
    const [logs, setLogs] = useState([]);
    const [news, setNews] = useState([]);
    const [isConnected, setIsConnected] = useState(false);
    const [currentPrice, setCurrentPrice] = useState(null);
    const [marketPrices, setMarketPrices] = useState({});
    const [priceColor, setPriceColor] = useState('var(--text-primary)');
    const [notifications, setNotifications] = useState([]);
    const [priceColors, setPriceColors] = useState({});

    // New State for Stock History & UI
    const [stockHistory, setStockHistory] = useState({}); // { SYMBOL: [{time, price}, ...] }
    const [selectedAgent, setSelectedAgent] = useState(null);

    const lastPriceRef = useRef(null);
    const prevPricesRef = useRef({});

    const addNotification = (message, type = 'info') => {
        const id = Date.now();
        setNotifications(prev => [...prev, { id, message, type }]);
        setTimeout(() => {
            setNotifications(prev => prev.filter(n => n.id !== id));
        }, 5000);
    };

    useEffect(() => {
        if (socket.connected) {
            console.log('socket already connected');
            setIsConnected(true);
            socket.emit('request_history');
        }

        socket.on('connect', () => {
            console.log('Connected to socket');
            setIsConnected(true);
            socket.emit('request_history');
        });

        socket.on('disconnect', () => {
            console.log('Disconnected');
            setIsConnected(false);
        });

        socket.on('chart_history_response', (history) => {
            const formatted = history.map(h => {
                const ts = Number(h.timestamp);
                const time = ts > 1000000000000 ? ts / 1000 : ts;
                return {
                    time: time,
                    price: h.price,
                    ...h.agents
                };
            }).sort((a, b) => a.time - b.time);

            setPriceData(formatted);

            if (formatted.length > 0) {
                const last = formatted[formatted.length - 1];
                lastPriceRef.current = last.price;
                setCurrentPrice(last.price);
            }
        });

        socket.on('chart_tick', (tick) => {
            // Legacy tick handler for single asset/general updates
            const newPrice = tick.price;
            lastPriceRef.current = newPrice;
            setCurrentPrice(newPrice);

            setPriceData(prev => {
                const ts = Number(tick.timestamp);
                const time = ts > 1000000000000 ? ts / 1000 : ts;
                const newPoint = { time: time, price: tick.price, ...tick.agents };
                return [...prev, newPoint];
            });
        });

        socket.on('leaderboard_update', (data) => {
            setAgents(data);
        });

        socket.on('trade_log', (log) => {
            setLogs(prev => [log, ...prev].slice(0, 50));
        });

        socket.on('tick_bundle', (bundle) => {
            const { market, chart, leaderboard } = bundle;

            // Update Stock Data (Multi-Asset)
            if (market && market.prices) {
                setMarketPrices(market.prices);

                // Update Colors
                const colorUpdates = {};
                Object.entries(market.prices).forEach(([sym, price]) => {
                    const prevPrice = prevPricesRef.current[sym];
                    if (prevPrice !== undefined) {
                        if (price > prevPrice) colorUpdates[sym] = '#00c853';
                        else if (price < prevPrice) colorUpdates[sym] = '#d50000';
                    }
                    prevPricesRef.current[sym] = price;
                });
                if (Object.keys(colorUpdates).length > 0) {
                    setPriceColors(prev => ({ ...prev, ...colorUpdates }));
                }

                // Update Stock History (Local Accumulation)
                const ts = Date.now() / 1000; // Use current time for sync
                setStockHistory(prev => {
                    const next = { ...prev };
                    Object.entries(market.prices).forEach(([sym, price]) => {
                        if (!next[sym]) next[sym] = [];
                        next[sym] = [...next[sym], { time: ts, price }].slice(-100); // Keep last 100 points
                    });
                    return next;
                });
            }

            // Update Equity Chart
            if (chart) {
                setPriceData(prev => {
                    const ts = Number(chart.timestamp);
                    const newTime = ts > 1000000000000 ? ts / 1000 : ts;
                    const exists = prev.find(p => Math.abs(p.time - newTime) < 0.001);
                    if (exists) {
                        return prev.map(p => Math.abs(p.time - newTime) < 0.001 ? { ...p, ...chart.agents, price: chart.price } : p);
                    }
                    return [...prev, { time: newTime, price: chart.price, ...chart.agents }].sort((a, b) => a.time - b.time);
                });
            }

            if (leaderboard) setAgents(leaderboard);
        });

        socket.on('news_update', (item) => {
            setNews(prev => [item, ...prev].slice(0, 50));
        });

        socket.on('agent_regenerating', (data) => {
            addNotification(`⚠️ Regenerating ${data.name}... Critique: ${data.critique.slice(0, 50)}...`, 'warning');
        });

        socket.on('agent_deployed', (data) => {
            addNotification(`🚀 ${data.name} Updated & Deployed!`, 'success');
        });

        api.get('/status').then(res => console.log("System Status:", res.data));

        return () => {
            socket.off('connect');
            socket.off('disconnect');
            socket.off('chart_tick');
            socket.off('leaderboard_update');
            socket.off('trade_log');
            socket.off('tick_bundle');
            socket.off('agent_regenerating');
            socket.off('agent_deployed');
        };
    }, []);

    // Helper to get color for stock chart
    const getStockColor = (sym) => {
        // Deterministic color hash or specific mapping
        const colors = ['#2962ff', '#ff9800', '#00c853', '#d500f9', '#00bcd4', '#ff3d00'];
        const hash = sym.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
        return colors[hash % colors.length];
    };

    return (
        <div className="dashboard-grid">
            {/* Modal */}
            {selectedAgent && (
                <AgentDetailModal
                    agent={selectedAgent}
                    onClose={() => setSelectedAgent(null)}
                    logs={logs}
                />
            )}

            {/* Notifications */}
            <div style={{ position: 'fixed', top: '20px', right: '20px', zIndex: 1000, display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {notifications.map(n => (
                    <div key={n.id} style={{
                        padding: '15px 20px',
                        background: n.type === 'success' ? 'rgba(0, 200, 83, 0.9)' : n.type === 'warning' ? 'rgba(255, 171, 0, 0.9)' : 'rgba(41, 98, 255, 0.9)',
                        color: '#fff',
                        borderRadius: '8px',
                        backdropFilter: 'blur(10px)',
                        boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
                        animation: 'fadeIn 0.3s ease',
                        maxWidth: '400px'
                    }}>
                        <div style={{ fontWeight: 'bold', marginBottom: '4px', fontSize: '0.8rem', opacity: 0.8 }}>
                            {n.type === 'success' ? 'SUCCESS' : n.type === 'warning' ? 'REGENERATING' : 'INFO'}
                        </div>
                        <div style={{ fontSize: '0.9rem' }}>{n.message}</div>
                    </div>
                ))}
            </div>

            <header className="header glass-panel" style={{ zIndex: 100 }}>
                <div className="logo" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    ALGO<span style={{ color: 'var(--accent-orange)' }}>CLASH</span> LIVE
                    <span style={{
                        fontSize: '0.7rem',
                        padding: '2px 6px',
                        background: isConnected ? 'rgba(0, 200, 83, 0.2)' : 'rgba(213, 0, 0, 0.2)',
                        color: isConnected ? '#00c853' : '#d50000',
                        borderRadius: '4px',
                        border: isConnected ? '1px solid rgba(0, 200, 83, 0.3)' : '1px solid rgba(213, 0, 0, 0.3)'
                    }}>
                        {isConnected ? 'ONLINE' : 'OFFLINE'}
                    </span>
                </div>
            </header>

            {/* TOP ROW: Equity Chart */}
            <div className="glass-panel" style={{ gridColumn: '1 / 3', gridRow: '2 / 3', padding: '15px', display: 'flex', flexDirection: 'column' }}>
                <LiveChart data={priceData} agents={agents} />
            </div>

            {/* BOTTOM LEFT: Stock Charts (Grid) */}
            <div className="glass-panel" style={{ gridColumn: '1 / 2', gridRow: '3 / 4', padding: '15px', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                <h3 style={{ margin: '0 0 15px 0', fontSize: '0.9rem', color: 'var(--text-secondary)', display: 'flex', justifyContent: 'space-between' }}>
                    MARKET OVERVIEW
                </h3>
                <div style={{
                    flex: 1,
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                    gap: '15px',
                    overflowY: 'auto',
                    paddingRight: '5px'
                }}>
                    {Object.keys(stockHistory).length > 0 ? (
                        Object.entries(stockHistory).map(([sym, history]) => (
                            <div key={sym} style={{ height: '150px', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', padding: '10px' }}>
                                <StockChart data={history} symbol={sym} color={getStockColor(sym)} />
                            </div>
                        ))
                    ) : (
                        <div style={{ padding: '20px', color: 'var(--text-secondary)', gridColumn: '1/-1', textAlign: 'center' }}>
                            Waiting for market data...
                        </div>
                    )}
                </div>
            </div>

            {/* BOTTOM RIGHT: Agents & Logs */}
            <div style={{ gridColumn: '2 / 3', gridRow: '3 / 4', display: 'flex', flexDirection: 'column', gap: '16px' }}>

                {/* Active Agents List */}
                <div className="glass-panel" style={{ flex: '0 0 auto', maxHeight: '50%', padding: '15px', display: 'flex', flexDirection: 'column' }}>
                    <h3 style={{ margin: '0 0 10px 0', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>ACTIVE AGENTS</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', overflowY: 'auto', flex: 1 }}>
                        {agents.map(agent => (
                            <div
                                key={agent.name}
                                onClick={() => setSelectedAgent(agent)}
                                style={{
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: '4px',
                                    padding: '10px',
                                    background: 'rgba(255,255,255,0.03)',
                                    borderRadius: '6px',
                                    cursor: 'pointer',
                                    transition: 'background 0.2s'
                                }}
                                onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.08)'}
                                onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.03)'}
                            >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <div style={{ fontWeight: 'bold', fontSize: '0.9rem' }}>{agent.name}</div>
                                    <div style={{
                                        color: (agent.equity - 100) >= 0 ? '#00c853' : '#d50000',
                                        fontWeight: 'bold',
                                        fontSize: '0.9rem'
                                    }}>
                                        ${agent.equity.toFixed(2)}
                                    </div>
                                </div>
                                <div style={{ display: 'flex', gap: '10px', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                    <span>W: <span style={{ color: '#fff' }}>{agent.win_rate || 0}%</span></span>
                                    <span>S: <span style={{ color: '#fff' }}>{agent.sharpe || 0}</span></span>
                                    <span>T: <span style={{ color: '#fff' }}>{agent.trades || 0}</span></span>
                                </div>
                            </div>
                        ))}
                        {agents.length === 0 && <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>No agents active.</div>}
                    </div>
                </div>

                {/* Recent Trade Log */}
                <div className="glass-panel" style={{ flex: 1, padding: '15px', display: 'flex', gap: '15px', overflow: 'hidden' }}>
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                        <h3 style={{ margin: '0 0 10px 0', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>RECENT TRADES</h3>
                        <TradeLog logs={logs} />
                    </div>
                    <div style={{ width: '350px', display: 'flex', flexDirection: 'column', overflow: 'hidden', borderLeft: '1px solid rgba(255,255,255,0.1)', paddingLeft: '15px' }}>
                        <h3 style={{ margin: '0 0 10px 0', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>LIVE NEWS & SENTIMENT</h3>
                        <NewsFeed news={news} />
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Dashboard;
