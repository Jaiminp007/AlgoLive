import { useEffect, useState, useRef, useMemo } from 'react';
import { socket, api } from '../api';
import { Link } from 'react-router-dom';
import LiveChart from './LiveChart';
import TradeLog from './TradeLog';
import StockChart from './StockChart';
import AgentDetailModal from './AgentDetailModal';
import NewsFeed from './NewsFeed';

// Agent colors matching Midnight Terminal palette
const AGENT_COLORS = ['#10b981', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16'];

const Dashboard = () => {
    const [priceData, setPriceData] = useState([]);
    const [agents, setAgents] = useState([]);
    const [logs, setLogs] = useState([]);
    const [news, setNews] = useState([]);
    const [isConnected, setIsConnected] = useState(false);
    const [currentPrice, setCurrentPrice] = useState(null);
    const [marketPrices, setMarketPrices] = useState({});
    const [priceColors, setPriceColors] = useState({});
    const [notifications, setNotifications] = useState([]);
    const [stockHistory, setStockHistory] = useState({});
    const [selectedAgent, setSelectedAgent] = useState(null);
    const [timeRange, setTimeRange] = useState('ALL');

    // Market status tabs
    const [marketTab, setMarketTab] = useState('live'); // 'live' or 'closed'
    const [stockMarketOpen, setStockMarketOpen] = useState(null); // null = unknown, true/false from backend

    const lastPriceRef = useRef(null);
    const prevPricesRef = useRef({});

    // Crypto symbols (always live)
    const CRYPTO_SYMBOLS = ['BTC', 'ETH', 'SOL', 'BNB'];

    // Stock symbols
    const STOCK_SYMBOLS = ['AAPL', 'TSLA', 'NVDA', 'MSFT', 'GOOGL', 'AMZN', 'META'];

    // Calculate stats
    const stats = useMemo(() => {
        // Total equity across all agents
        const totalEquity = agents.reduce((sum, a) => sum + (a.equity || 10000), 0);
        const startingEquity = agents.length * 10000;
        const totalPnL = totalEquity - startingEquity;
        const totalPnLPercent = startingEquity > 0 ? (totalPnL / startingEquity * 100) : 0;

        const avgRoi = agents.length > 0
            ? agents.reduce((sum, a) => sum + (a.roi || 0), 0) / agents.length
            : 0;
        const totalTrades = agents.reduce((sum, a) => sum + (a.trades || 0), 0);
        const todayTrades = logs.filter(l => {
            const logTime = new Date(l.timestamp * 1000);
            const today = new Date();
            return logTime.toDateString() === today.toDateString();
        }).length;

        return {
            totalEquity: totalEquity > 1000000 ? `$${(totalEquity / 1000000).toFixed(2)}M` : `$${(totalEquity / 1000).toFixed(1)}K`,
            totalPnLPercent: totalPnLPercent.toFixed(2),
            activeAgents: agents.length,
            avgRoi: avgRoi.toFixed(2),
            totalTrades,
            todayTrades
        };
    }, [agents, logs]);

    const addNotification = (message, type = 'info') => {
        const id = Date.now();
        setNotifications(prev => [...prev, { id, message, type }]);
        setTimeout(() => {
            setNotifications(prev => prev.filter(n => n.id !== id));
        }, 5000);
    };

    // Get color for agent by index
    const getAgentColor = (index) => AGENT_COLORS[index % AGENT_COLORS.length];

    useEffect(() => {
        if (socket.connected) {
            setIsConnected(true);
            socket.emit('request_history');
        }

        socket.on('connect', () => {
            setIsConnected(true);
            socket.emit('request_history');
        });

        socket.on('disconnect', () => {
            setIsConnected(false);
        });

        socket.on('chart_history_response', (history) => {
            const formatted = history.map(h => {
                const ts = Number(h.timestamp);
                const time = ts > 1000000000000 ? ts / 1000 : ts;
                return { time, price: h.price, ...h.agents };
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
            lastPriceRef.current = newPrice;
            setCurrentPrice(newPrice);

            setPriceData(prev => {
                const ts = Number(tick.timestamp);
                const time = ts > 1000000000000 ? ts / 1000 : ts;
                return [...prev, { time, price: tick.price, ...tick.agents }];
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

            if (market && market.prices) {
                setMarketPrices(market.prices);

                // Capture stock market status from backend
                if (market.prices._stock_market_open !== undefined) {
                    setStockMarketOpen(market.prices._stock_market_open);
                }

                const colorUpdates = {};
                Object.entries(market.prices).forEach(([sym, price]) => {
                    // Skip metadata keys
                    if (sym.startsWith('_')) return;

                    const prevPrice = prevPricesRef.current[sym];
                    if (prevPrice !== undefined) {
                        if (price > prevPrice) colorUpdates[sym] = 'profit';
                        else if (price < prevPrice) colorUpdates[sym] = 'loss';
                    }
                    prevPricesRef.current[sym] = price;
                });
                if (Object.keys(colorUpdates).length > 0) {
                    setPriceColors(prev => ({ ...prev, ...colorUpdates }));
                }

                const ts = Date.now() / 1000;
                setStockHistory(prev => {
                    const next = { ...prev };
                    Object.entries(market.prices).forEach(([sym, price]) => {
                        // Skip metadata keys
                        if (sym.startsWith('_')) return;

                        if (!next[sym]) next[sym] = [];
                        next[sym] = [...next[sym], { time: ts, price }].slice(-100);
                    });
                    return next;
                });
            }

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
            addNotification(`Regenerating ${data.name}... Critique: ${data.critique.slice(0, 50)}...`, 'warning');
        });

        socket.on('agent_deployed', (data) => {
            addNotification(`${data.name} Updated & Deployed!`, 'success');
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

    // Determine if market is open (uses backend status or fallback calculation)
    const isMarketOpen = (symbol) => {
        // Crypto is always open
        if (CRYPTO_SYMBOLS.includes(symbol)) return true;

        // For stocks, use backend status if available
        if (stockMarketOpen !== null) {
            return stockMarketOpen;
        }

        // Fallback: calculate locally (Eastern Time)
        const now = new Date();
        // Convert to ET by creating a date string in ET timezone
        const etTimeStr = now.toLocaleString('en-US', { timeZone: 'America/New_York' });
        const etDate = new Date(etTimeStr);

        const hour = etDate.getHours();
        const minute = etDate.getMinutes();
        const day = etDate.getDay();

        // Weekday check (Mon=1, Fri=5)
        if (day === 0 || day === 6) return false;

        // Market hours: 9:30 AM - 4:30 PM ET
        const timeInMinutes = hour * 60 + minute;
        const openTime = 9 * 60 + 30;  // 9:30 AM
        const closeTime = 16 * 60 + 30; // 4:30 PM

        return timeInMinutes >= openTime && timeInMinutes <= closeTime;
    };

    // Get price change percentage
    const getPriceChange = (sym) => {
        const history = stockHistory[sym];
        if (!history || history.length < 2) return null;
        const first = history[0].price;
        const last = history[history.length - 1].price;
        return ((last - first) / first * 100).toFixed(2);
    };

    // Filter symbols by market status for tabs
    const getLiveSymbols = () => {
        return Object.keys(stockHistory).filter(sym => {
            if (CRYPTO_SYMBOLS.includes(sym)) return true; // Crypto always live
            return isMarketOpen(sym); // Stocks only if market open
        });
    };

    const getClosedSymbols = () => {
        return Object.keys(stockHistory).filter(sym => {
            if (CRYPTO_SYMBOLS.includes(sym)) return false; // Crypto never closed
            return !isMarketOpen(sym); // Stocks only if market closed
        });
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
                    <div key={n.id} className={`notification notification-${n.type}`}>
                        <div style={{ fontWeight: '600', marginBottom: '4px', fontSize: '0.7rem', opacity: 0.8, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                            {n.type === 'success' ? 'SUCCESS' : n.type === 'warning' ? 'REGENERATING' : 'INFO'}
                        </div>
                        <div style={{ fontSize: '0.875rem' }}>{n.message}</div>
                    </div>
                ))}
            </div>

            {/* Header */}
            <header className="header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span className="logo">
                        AlgoClash <span style={{ color: 'var(--accent-primary)' }}>Live</span>
                    </span>
                    <span className={`badge ${isConnected ? 'badge-online' : 'badge-offline'}`}>
                        <span style={{
                            width: '6px',
                            height: '6px',
                            borderRadius: '50%',
                            background: isConnected ? 'var(--profit)' : 'var(--loss)',
                            display: 'inline-block'
                        }}></span>
                        {isConnected ? 'Online' : 'Offline'}
                    </span>
                </div>
                <nav className="nav-links">
                    <Link to="/dashboard" className="nav-link active">Dashboard</Link>
                    <Link to="/leaderboard" className="nav-link">Leaderboard</Link>
                    <Link to="/sandbox" className="nav-link" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        Sandbox
                        <span style={{
                            fontSize: '0.6rem',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            background: 'var(--accent-primary)',
                            color: 'var(--bg-base)',
                            fontWeight: '700',
                            letterSpacing: '0.5px'
                        }}>BETA</span>
                    </Link>
                    <a href="mailto:contact@algoclash.com?subject=AlgoClash%20Inquiry" className="nav-link">Contact</a>
                </nav>
            </header>

            {/* Stats Row */}
            <div className="stats-row">
                <div className="stat-card">
                    <div className="stat-label">Total Equity</div>
                    <div className="stat-value">
                        {stats.totalEquity}
                        <span className={`stat-change ${parseFloat(stats.totalPnLPercent) >= 0 ? 'positive' : 'negative'}`}>
                            {parseFloat(stats.totalPnLPercent) >= 0 ? '+' : ''}{stats.totalPnLPercent}%
                        </span>
                    </div>
                </div>
                <div className="stat-card">
                    <div className="stat-label">Active Agents</div>
                    <div className="stat-value">{stats.activeAgents}</div>
                </div>
                <div className="stat-card">
                    <div className="stat-label">Avg ROI</div>
                    <div className="stat-value" style={{ color: parseFloat(stats.avgRoi) >= 0 ? 'var(--profit)' : 'var(--loss)' }}>
                        {parseFloat(stats.avgRoi) >= 0 ? '+' : ''}{stats.avgRoi}%
                    </div>
                </div>
                <div className="stat-card">
                    <div className="stat-label">Total Trades</div>
                    <div className="stat-value">
                        {stats.totalTrades}
                        <span className="stat-change positive">+{stats.todayTrades} today</span>
                    </div>
                </div>
            </div>

            {/* Main Chart Area */}
            <div className="glass-panel" style={{ gridColumn: '1 / 2', gridRow: '3 / 4', padding: '20px', display: 'flex', flexDirection: 'column' }}>
                <div className="section-header">
                    <div>
                        <div className="section-title">Agent Equity Comparison</div>
                        <div className="section-subtitle">Real-time portfolio performance</div>
                    </div>
                    <div className="time-selector">
                        {['1H', '4H', '1D', 'ALL'].map(t => (
                            <button
                                key={t}
                                className={`time-btn ${timeRange === t ? 'active' : ''}`}
                                onClick={() => setTimeRange(t)}
                            >
                                {t}
                            </button>
                        ))}
                    </div>
                </div>
                <div style={{ flex: 1, minHeight: 0 }}>
                    <LiveChart data={priceData} agents={agents} timeRange={timeRange} />
                </div>
            </div>

            {/* Right Sidebar: Active Agents + Recent Trades */}
            <div style={{ gridColumn: '2 / 3', gridRow: '3 / 4', display: 'flex', flexDirection: 'column', gap: '16px', minHeight: '500px', height: '100%' }}>
                {/* Active Agents */}
                <div className="glass-panel" style={{ flex: '0 0 auto', padding: '20px', maxHeight: '320px', overflow: 'hidden' }}>
                    <div className="section-header">
                        <div className="section-title">Active Agents</div>
                        <Link to="/" style={{ color: 'var(--accent-primary)', fontSize: '0.75rem', textDecoration: 'none' }}>+ Add</Link>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxHeight: '220px', overflowY: 'auto' }}>
                        {agents.map((agent, index) => {
                            const roi = agent.roi || ((agent.equity - 10000) / 10000 * 100);
                            const isProfit = roi >= 0;
                            return (
                                <div
                                    key={agent.name}
                                    onClick={() => setSelectedAgent(agent)}
                                    style={{
                                        padding: '12px',
                                        background: 'rgba(17, 24, 39, 0.5)',
                                        borderRadius: '8px',
                                        cursor: 'pointer',
                                        transition: 'background 0.2s',
                                        borderLeft: `3px solid ${getAgentColor(index)}`
                                    }}
                                    onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(31, 41, 55, 0.5)'}
                                    onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(17, 24, 39, 0.5)'}
                                >
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                            <span style={{
                                                width: '8px',
                                                height: '8px',
                                                borderRadius: '50%',
                                                background: getAgentColor(index)
                                            }}></span>
                                            <span style={{ fontWeight: '500', color: 'var(--text-primary)', fontSize: '0.9rem' }}>{agent.name}</span>
                                        </div>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                            <span className={`badge ${isProfit ? 'badge-profit' : 'badge-loss'}`}>
                                                {isProfit ? '+' : ''}{roi.toFixed(2)}%
                                            </span>
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    if (window.confirm(`Remove ${agent.name} from the arena?`)) {
                                                        api.post('/stop_agent', { name: agent.name })
                                                            .then(() => {
                                                                addNotification(`${agent.name} removed from arena`, 'info');
                                                            })
                                                            .catch(err => {
                                                                addNotification(`Failed to remove ${agent.name}: ${err.message}`, 'warning');
                                                            });
                                                    }
                                                }}
                                                style={{
                                                    background: 'transparent',
                                                    border: 'none',
                                                    color: 'var(--text-muted)',
                                                    cursor: 'pointer',
                                                    padding: '2px 6px',
                                                    fontSize: '1rem',
                                                    borderRadius: '4px',
                                                    transition: 'all 0.2s',
                                                    lineHeight: '1'
                                                }}
                                                onMouseEnter={(e) => {
                                                    e.currentTarget.style.background = 'rgba(239, 68, 68, 0.2)';
                                                    e.currentTarget.style.color = '#ef4444';
                                                }}
                                                onMouseLeave={(e) => {
                                                    e.currentTarget.style.background = 'transparent';
                                                    e.currentTarget.style.color = 'var(--text-muted)';
                                                }}
                                                title="Remove agent"
                                            >
                                                ×
                                            </button>
                                        </div>
                                    </div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                                        <span style={{ fontSize: '1.25rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                                            ${agent.equity?.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 }) || '10,000'}
                                        </span>
                                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                            {agent.trades || 0} trades
                                        </span>
                                    </div>
                                </div>
                            );
                        })}
                        {agents.length === 0 && (
                            <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem', padding: '20px', textAlign: 'center' }}>
                                No agents active. <Link to="/" style={{ color: 'var(--accent-primary)' }}>Deploy one</Link>
                            </div>
                        )}
                    </div>
                </div>

                {/* Recent Trades */}
                <div className="glass-panel" style={{ flex: '1 1 auto', minHeight: '280px', padding: '20px', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                    <div className="section-header">
                        <div className="section-title">Recent Trades</div>
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>View All</span>
                    </div>
                    <div style={{ flex: 1, overflow: 'auto', minHeight: '180px' }}>
                        <TradeLog logs={logs.slice(0, 10)} />
                    </div>
                </div>
            </div>

            {/* Market Overview */}
            <div className="glass-panel" style={{ gridColumn: '1 / -1', gridRow: '4 / 5', padding: '16px', display: 'flex', flexDirection: 'column' }}>
                <div className="section-header" style={{ marginBottom: '12px' }}>
                    <div className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                        Market Overview
                        {/* Tab Buttons */}
                        <div style={{ display: 'flex', gap: '8px' }}>
                            <button
                                onClick={() => setMarketTab('live')}
                                style={{
                                    padding: '6px 12px',
                                    fontSize: '0.75rem',
                                    fontWeight: '600',
                                    borderRadius: '6px',
                                    border: 'none',
                                    cursor: 'pointer',
                                    background: marketTab === 'live' ? 'var(--accent-primary)' : 'rgba(255,255,255,0.1)',
                                    color: marketTab === 'live' ? 'var(--bg-base)' : 'var(--text-muted)',
                                    transition: 'all 0.2s'
                                }}
                            >
                                <span style={{
                                    display: 'inline-block',
                                    width: '6px',
                                    height: '6px',
                                    borderRadius: '50%',
                                    background: '#10b981',
                                    marginRight: '6px',
                                    animation: 'pulse 2s infinite'
                                }}></span>
                                Live Markets ({getLiveSymbols().length})
                            </button>
                            <button
                                onClick={() => setMarketTab('closed')}
                                style={{
                                    padding: '6px 12px',
                                    fontSize: '0.75rem',
                                    fontWeight: '600',
                                    borderRadius: '6px',
                                    border: 'none',
                                    cursor: 'pointer',
                                    background: marketTab === 'closed' ? 'rgba(156, 163, 175, 0.3)' : 'rgba(255,255,255,0.1)',
                                    color: marketTab === 'closed' ? 'var(--text-primary)' : 'var(--text-muted)',
                                    transition: 'all 0.2s'
                                }}
                            >
                                Closed Markets ({getClosedSymbols().length})
                            </button>
                        </div>
                    </div>
                    {marketTab === 'closed' && (
                        <span style={{
                            fontSize: '0.7rem',
                            color: 'var(--text-muted)',
                            background: 'rgba(156, 163, 175, 0.2)',
                            padding: '4px 8px',
                            borderRadius: '4px'
                        }}>
                            Cached prices • No API calls
                        </span>
                    )}
                </div>
                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                    gap: '12px'
                }}>
                    {(() => {
                        const symbols = marketTab === 'live' ? getLiveSymbols() : getClosedSymbols();

                        if (symbols.length === 0 && Object.keys(stockHistory).length > 0) {
                            return (
                                <div style={{
                                    gridColumn: '1 / -1',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    color: 'var(--text-muted)',
                                    padding: '30px'
                                }}>
                                    {marketTab === 'live' ? (
                                        <>
                                            <span style={{ fontSize: '2rem', marginBottom: '8px' }}>🌙</span>
                                            <span>Stock market is closed</span>
                                            <span style={{ fontSize: '0.75rem', marginTop: '4px' }}>
                                                View Closed Markets tab for last known prices
                                            </span>
                                        </>
                                    ) : (
                                        <>
                                            <span style={{ fontSize: '2rem', marginBottom: '8px' }}>☀️</span>
                                            <span>All markets are open!</span>
                                            <span style={{ fontSize: '0.75rem', marginTop: '4px' }}>
                                                Switch to Live Markets for real-time data
                                            </span>
                                        </>
                                    )}
                                </div>
                            );
                        }

                        if (symbols.length === 0) {
                            return (
                                <div style={{
                                    gridColumn: '1 / -1',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    color: 'var(--text-muted)',
                                    padding: '20px'
                                }}>
                                    Waiting for market data...
                                </div>
                            );
                        }

                        return symbols.map(sym => {
                            const history = stockHistory[sym];
                            if (!history) return null;

                            const change = getPriceChange(sym);
                            const isUp = change && parseFloat(change) >= 0;
                            const open = isMarketOpen(sym);
                            const currentPriceVal = history[history.length - 1]?.price;

                            return (
                                <div
                                    key={sym}
                                    className={`market-card ${!open ? 'closed' : ''}`}
                                    style={{
                                        display: 'flex',
                                        flexDirection: 'column',
                                        padding: '14px',
                                        height: '130px'
                                    }}
                                >
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                                        <span style={{
                                            fontSize: '0.7rem',
                                            fontWeight: '600',
                                            color: 'var(--text-muted)',
                                            textTransform: 'uppercase',
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '4px'
                                        }}>
                                            {sym}
                                            {!open && (
                                                <span style={{
                                                    fontSize: '0.6rem',
                                                    background: 'rgba(156, 163, 175, 0.3)',
                                                    padding: '1px 4px',
                                                    borderRadius: '3px'
                                                }}>CACHED</span>
                                            )}
                                            {CRYPTO_SYMBOLS.includes(sym) && (
                                                <span style={{
                                                    fontSize: '0.6rem',
                                                    background: 'rgba(16, 185, 129, 0.2)',
                                                    color: '#10b981',
                                                    padding: '1px 4px',
                                                    borderRadius: '3px'
                                                }}>24/7</span>
                                            )}
                                        </span>
                                        {change && (
                                            <span style={{
                                                color: isUp ? 'var(--profit)' : 'var(--loss)',
                                                fontSize: '0.75rem',
                                                fontWeight: '600'
                                            }}>
                                                {isUp ? '↑' : '↓'} {Math.abs(parseFloat(change))}%
                                            </span>
                                        )}
                                    </div>
                                    <div style={{ fontSize: '1.1rem', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '8px' }}>
                                        ${currentPriceVal?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}
                                    </div>
                                    <div style={{ flex: 1, minHeight: '45px' }}>
                                        <StockChart
                                            data={history}
                                            symbol={sym}
                                            color={isUp ? 'var(--profit)' : 'var(--loss)'}
                                        />
                                    </div>
                                </div>
                            );
                        });
                    })()}
                </div>
            </div>
        </div>
    );
};

export default Dashboard;
