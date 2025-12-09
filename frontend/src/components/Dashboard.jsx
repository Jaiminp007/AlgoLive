import { useEffect, useState, useRef } from 'react';
import { socket, api } from '../api';
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
    const [priceColor, setPriceColor] = useState('var(--text-primary)');
    const lastPriceRef = useRef(null);

    useEffect(() => {
        socket.on('connect', () => {
            console.log('Connected to socket');
            setIsConnected(true);
            // Request full history for "Start from Starting" view
            socket.emit('request_history');
        });

        socket.on('disconnect', () => {
            console.log('Disconnected');
            setIsConnected(false);
        });

        socket.on('chart_history_response', (history) => {
            console.log("Received History Points:", history.length);
            // Format history to match setPriceData structure if needed, 
            // but backend sends same payload format as tick, just need to transform time?
            // Tick: { timestamp: ms, price, agents: {} }
            // Frontend expects: { time: seconds, price, ...agents }

            const formatted = history.map(h => ({
                time: h.timestamp / 1000,
                price: h.price,
                ...h.agents
            }));

            setPriceData(formatted);

            // Set last price ref from last point
            if (history.length > 0) {
                const last = history[history.length - 1];
                lastPriceRef.current = last.price;
                setCurrentPrice(last.price);
            }
        });

        socket.on('chart_tick', (tick) => {
            const newPrice = tick.price;
            const lastPrice = lastPriceRef.current;

            if (lastPrice !== null) {
                if (newPrice > lastPrice) {
                    setPriceColor('#00c853'); // Green
                } else if (newPrice < lastPrice) {
                    setPriceColor('#d50000'); // Red
                }
                // If equal, keep previous color
            } else {
                setPriceColor('#00c853'); // Default to green on first load if logic applies, or keep text-primary
            }

            lastPriceRef.current = newPrice;
            setCurrentPrice(newPrice);

            setPriceData(prev => {
                const newPoint = {
                    time: new Date(tick.timestamp).getTime() / 1000,
                    price: tick.price,
                    ...tick.agents // Spread agent equities: { AgentA: 100000, AgentB: 102000 }
                };
                const newData = [...prev, newPoint];
                // if (newData.length > 50) return newData.slice(-50); // Keep last 50 points for better visibility
                // Removed slicing to show full history as per request
                return newData;
            });
        });

        socket.on('leaderboard_update', (data) => {
            console.log("Leaderboard Update Received:", data);
            setAgents(data);
        });

        socket.on('trade_log', (log) => {
            setLogs(prev => [log, ...prev].slice(0, 50));
        });

        // Initial Status Check
        api.get('/status').then(res => {
            console.log("System Status:", res.data);
            if (res.data.active_agents) {
                // We might want to fetch full agent details here
            }
        });

        return () => {
            socket.off('connect');
            socket.off('disconnect');
            socket.off('chart_tick');
            socket.off('leaderboard_update');
            socket.off('trade_log');
        };
    }, []);

    return (
        <div className="dashboard-grid">
            <header className="header glass-panel">
                <div className="logo">ALGO<span style={{ color: 'var(--accent-orange)' }}>CLASH</span> LIVE</div>
                <div style={{ textAlign: 'right' }}>
                    <div style={{
                        color: isConnected ? '#00c853' : '#d50000',
                        fontWeight: 'bold',
                        fontSize: '0.8rem',
                        marginBottom: '4px'
                    }}>
                        {isConnected ? '● LIVE' : '○ DISCONNECTED'}
                    </div>
                    {currentPrice && (
                        <div style={{
                            fontSize: '1.2rem',
                            fontWeight: 'bold',
                            color: priceColor,
                            transition: 'color 0.3s ease'
                        }}>
                            BTC: ${currentPrice.toFixed(2)}
                        </div>
                    )}
                </div>
            </header>

            <div className="main-chart glass-panel" style={{ gridColumn: '1 / 2', gridRow: '2 / 4', padding: '10px' }}>
                <LiveChart data={priceData} agents={agents} />
            </div>

            <div className="leaderboard glass-panel" style={{ gridColumn: '2 / 3', gridRow: '2 / 3', padding: '10px', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                <Leaderboard agents={agents} />
            </div>

            <div className="control-panel glass-panel" style={{ gridColumn: '2 / 3', gridRow: '3 / 4', padding: '10px', display: 'flex', flexDirection: 'column', gap: '10px', overflow: 'hidden' }}>
                <ControlPanel />
                <div style={{ flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                    <h3 style={{ margin: '0 0 10px 0', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>TRADE LOG</h3>
                    <TradeLog logs={logs} />
                </div>
            </div>
        </div>
    );
};

export default Dashboard;
