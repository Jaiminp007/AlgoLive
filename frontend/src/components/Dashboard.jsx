import { useEffect, useState, useRef } from 'react';
import { socket, api } from '../api';
import { Link } from 'react-router-dom';
import LiveChart from './LiveChart';
import Leaderboard from './Leaderboard';
import TradeLog from './TradeLog';
import ControlPanel from './ControlPanel';

const Dashboard = () => {
    const [priceData, setPriceData] = useState([]);
    const [agents, setAgents] = useState([]);
    const [logs, setLogs] = useState([]);
    const [isConnected, setIsConnected] = useState(false);
    const [currentPrice, setCurrentPrice] = useState(null);
    const [marketPrices, setMarketPrices] = useState({}); // New state for multi-asset
    const [priceColor, setPriceColor] = useState('var(--text-primary)');
    const [notifications, setNotifications] = useState([]); // Array of {id, message, type}
    const [priceColors, setPriceColors] = useState({}); // { SYMBOL: '#color' }
    const lastPriceRef = useRef(null);
    const prevPricesRef = useRef({}); // { SYMBOL: price }

    const addNotification = (message, type = 'info') => {
        const id = Date.now();
        setNotifications(prev => [...prev, { id, message, type }]);
        // Auto remove after 5s
        setTimeout(() => {
            setNotifications(prev => prev.filter(n => n.id !== id));
        }, 5000);
    };

    useEffect(() => {
        // Check initial state
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
                // Auto-detect MS vs S (Cutoff 1e12 ~ Year 2001)
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
            const newPrice = tick.price;
            const lastPrice = lastPriceRef.current;

            if (lastPrice !== null) {
                if (newPrice > lastPrice) {
                    setPriceColor('#00c853');
                } else if (newPrice < lastPrice) {
                    setPriceColor('#d50000');
                }
            } else {
                setPriceColor('#00c853');
            }

            lastPriceRef.current = newPrice;
            setCurrentPrice(newPrice);

            setPriceData(prev => {
                const ts = Number(tick.timestamp);
                const time = ts > 1000000000000 ? ts / 1000 : ts;

                const newPoint = {
                    time: time,
                    price: tick.price,
                    ...tick.agents
                };
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

            // Update price from market tick (Multi-Asset support)
            if (market) {
                if (market.prices) {
                    setMarketPrices(market.prices);

                    // Update colors based on price changes
                    const colorUpdates = {};
                    Object.entries(market.prices).forEach(([sym, price]) => {
                        const prevPrice = prevPricesRef.current[sym];
                        if (prevPrice !== undefined) {
                            if (price > prevPrice) colorUpdates[sym] = '#00c853'; // Green
                            else if (price < prevPrice) colorUpdates[sym] = '#d50000'; // Red
                        }
                        prevPricesRef.current[sym] = price;
                    });

                    if (Object.keys(colorUpdates).length > 0) {
                        setPriceColors(prev => ({ ...prev, ...colorUpdates }));
                    }

                    // Maintain currentPrice as BTC for legacy/other components if needed
                    if (market.prices['BTC']) {
                        const newPrice = market.prices['BTC'];
                        const lastPrice = lastPriceRef.current;
                        if (lastPrice !== null) {
                            if (newPrice > lastPrice) setPriceColor('#00c853');
                            else if (newPrice < lastPrice) setPriceColor('#d50000');
                        }
                        lastPriceRef.current = newPrice;
                        setCurrentPrice(newPrice);
                    }
                } else if (market.price) {
                    // Legacy fallback
                    const newPrice = market.price;
                    const lastPrice = lastPriceRef.current;

                    if (lastPrice !== null) {
                        if (newPrice > lastPrice) {
                            setPriceColor('#00c853');
                        } else if (newPrice < lastPrice) {
                            setPriceColor('#d50000');
                        }
                    }
                    lastPriceRef.current = newPrice;
                    setCurrentPrice(newPrice);
                }
            }

            // Update chart data
            if (chart) {
                setPriceData(prev => {
                    const ts = Number(chart.timestamp);
                    const newTime = ts > 1000000000000 ? ts / 1000 : ts;

                    // Check if exists
                    const exists = prev.find(p => Math.abs(p.time - newTime) < 0.001);
                    if (exists) {
                        // Update existing point (prevent horizontal zigzag)
                        return prev.map(p => Math.abs(p.time - newTime) < 0.001 ? { ...p, ...chart.agents, price: chart.price } : p);
                    }

                    const newPoint = {
                        time: newTime,
                        price: chart.price,
                        ...chart.agents
                    };
                    return [...prev, newPoint].sort((a, b) => a.time - b.time); // Always sort just in case
                });
            }

            // Update leaderboard
            if (leaderboard) {
                setAgents(leaderboard);
            }
        });

        // REGENERATION EVENTS
        socket.on('agent_regenerating', (data) => {
            addNotification(`⚠️ Regenerating ${data.name}... Critique: ${data.critique.slice(0, 50)}...`, 'warning');
        });

        socket.on('agent_deployed', (data) => {
            addNotification(`🚀 ${data.name} Updated & Deployed!`, 'success');
        });

        api.get('/status').then(res => {
            console.log("System Status:", res.data);
        });

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

    return (
        <div className="dashboard-grid">
            {/* Notifications Container */}
            <div style={{ position: 'fixed', top: '20px', right: '20px', zIndex: 1000, display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {notifications.map(n => (
                    <div key={n.id} style={{
                        padding: '15px 20px',
                        background: n.type === 'success' ? 'rgba(0, 200, 83, 0.9)' : n.type === 'warning' ? 'rgba(255, 171, 0, 0.9)' : 'rgba(33, 150, 243, 0.9)',
                        color: '#fff',
                        borderRadius: '4px',
                        boxShadow: '0 4px 6px rgba(0,0,0,0.3)',
                        animation: 'fadeIn 0.3s ease',
                        borderLeft: '4px solid rgba(255,255,255,0.5)',
                        maxWidth: '400px'
                    }}>
                        <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>
                            {n.type === 'success' ? 'SUCCESS' : n.type === 'warning' ? 'REGENERATING' : 'INFO'}
                        </div>
                        <div style={{ fontSize: '0.9rem' }}>{n.message}</div>
                    </div>
                ))}
            </div>

            <header className="header glass-panel">
                <div className="logo">ALGO<span style={{ color: 'var(--accent-orange)' }}>CLASH</span> LIVE</div>

                <div style={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
                    <Link to="/leaderboard" style={{
                        color: 'var(--text-primary)',
                        textDecoration: 'none',
                        fontSize: '1.2rem',
                        fontWeight: 'bold',
                        padding: '10px 20px',
                        borderBottom: '2px solid var(--accent-orange)',
                        textTransform: 'uppercase',
                        letterSpacing: '1px'
                    }}>
                        Leaderboard
                    </Link>
                </div>

                <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'row', alignItems: 'center', gap: '20px' }}>
                    <div style={{
                        color: isConnected ? '#00c853' : '#d50000',
                        fontWeight: 'bold',
                        fontSize: '0.8rem',
                        marginRight: '10px'
                    }}>
                        {isConnected ? '● LIVE' : '○ DISCONNECTED'}
                    </div>
                    {marketPrices && Object.entries(marketPrices).length > 0 ? (
                        <div style={{
                            display: 'flex',
                            gap: '15px',
                            overflowX: 'auto',
                            maxWidth: '60vw',
                            paddingBottom: '5px',
                            whiteSpace: 'nowrap',
                            scrollbarWidth: 'none', /* Firefox */
                            msOverflowStyle: 'none'  /* IE 10+ */
                        }} className="hide-scrollbar">
                            <style>{`.hide-scrollbar::-webkit-scrollbar { display: none; }`}</style>
                            {Object.entries(marketPrices).map(([sym, price]) => (
                                <div key={sym} style={{
                                    fontSize: '0.9rem',
                                    fontWeight: 'bold',
                                    color: priceColors[sym] || 'var(--text-primary)',
                                    transition: 'color 0.5s ease',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '5px',
                                    background: 'rgba(255, 255, 255, 0.05)',
                                    padding: '4px 8px',
                                    borderRadius: '4px',
                                    flexShrink: 0
                                }}>
                                    <span style={{ color: 'var(--accent-orange)' }}>{sym}</span>
                                    <span>${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })}</span>
                                </div>
                            ))}
                        </div>
                    ) : (
                        currentPrice && (
                            <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: priceColor }}>
                                BTC: ${currentPrice.toFixed(2)}
                            </div>
                        )
                    )}
                </div>
            </header>

            <div className="main-chart glass-panel" style={{ gridColumn: '1 / 2', gridRow: '2 / 4', padding: '10px' }}>
                <LiveChart data={priceData} agents={agents} />
            </div>

            <div className="trade-log glass-panel" style={{ gridColumn: '2 / 3', gridRow: '2 / 3', padding: '10px', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                <h3 style={{ margin: '0 0 10px 0', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>TRADE LOG</h3>
                <TradeLog logs={logs} />
            </div>

            <div className="leaderboard-panel glass-panel" style={{ gridColumn: '2 / 3', gridRow: '3 / 4', padding: '10px', overflow: 'hidden', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <ControlPanel />
                <Leaderboard agents={agents} />
            </div>
        </div>
    );
};

export default Dashboard;
