import { useState, useEffect } from 'react';
import { socket } from '../api';
import { Link } from 'react-router-dom';
import { FaArrowLeft } from 'react-icons/fa';

const LeaderboardPage = () => {
    const [agents, setAgents] = useState([]);

    useEffect(() => {
        // Request immediate update
        if (socket.connected) {
            socket.emit('request_history'); // Triggers bundle usually
        }

        const handleUpdate = (data) => {
            setAgents(data);
        };

        const handleBundle = (bundle) => {
            if (bundle.leaderboard) {
                setAgents(bundle.leaderboard);
            }
        };

        socket.on('leaderboard_update', handleUpdate);
        socket.on('tick_bundle', handleBundle);

        return () => {
            socket.off('leaderboard_update', handleUpdate);
            socket.off('tick_bundle', handleBundle);
        };
    }, []);

    // Calculate Sharpe Ratio (simplified)
    // In a real app, this would be computed backend based on historical volatility
    const getSharpe = (roi) => {
        if (!roi) return "0.00";
        // Mock calc: ROI / Volatility (assumed constant for mock)
        return (roi / 5).toFixed(2);
    };

    return (
        <div className="leaderboard-page fade-in" style={{ padding: '40px', maxWidth: '1200px', margin: '0 auto', color: 'var(--text-primary)' }}>
            <header style={{ display: 'flex', alignItems: 'center', marginBottom: '40px' }}>
                <Link to="/dashboard" style={{ display: 'flex', alignItems: 'center', gap: '10px', color: 'var(--accent-blue)', textDecoration: 'none', fontSize: '1.2rem', fontWeight: 'bold' }}>
                    <FaArrowLeft /> Back to Dashboard
                </Link>
                <div className="logo" style={{ marginLeft: 'auto', fontSize: '2rem' }}>ALGO<span style={{ color: 'var(--accent-orange)' }}>CLASH</span> LEADERBOARD</div>
            </header>

            <div className="glass-panel" style={{ padding: '20px', overflowX: 'auto', display: 'flex', flexDirection: 'column' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                    <thead>
                        <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
                            <th style={{ padding: '15px' }}>Rank</th>
                            <th style={{ padding: '15px' }}>Agent Name</th>
                            <th style={{ padding: '15px', textAlign: 'right' }}>Equity ($)</th>
                            <th style={{ padding: '15px', textAlign: 'right' }}>ROI (%)</th>
                            <th style={{ padding: '15px', textAlign: 'right' }}>Cash ($)</th>
                            <th style={{ padding: '15px', textAlign: 'right', color: '#00c853' }}>Profit ($)</th>
                            {/* <th style={{ padding: '15px', textAlign: 'right' }}>Sharpe</th> */}
                            <th style={{ padding: '15px', textAlign: 'right' }}>Total Fees ($)</th>
                            <th style={{ padding: '15px', textAlign: 'right' }}>BTC</th>
                            <th style={{ padding: '15px', textAlign: 'right' }}>ETH</th>
                            <th style={{ padding: '15px', textAlign: 'right' }}>SOL</th>
                            <th style={{ padding: '15px', textAlign: 'right' }}>XRP</th>
                            <th style={{ padding: '15px', textAlign: 'right' }}>BNB</th>
                            <th style={{ padding: '15px', textAlign: 'right' }}>ZEC</th>
                            <th style={{ padding: '15px', textAlign: 'right' }}>DOGE</th>
                            <th style={{ padding: '15px', textAlign: 'right' }}>TRX</th>
                            <th style={{ padding: '15px', textAlign: 'right' }}>SUI</th>
                            <th style={{ padding: '15px', textAlign: 'right' }}>LINK</th>
                            <th style={{ padding: '15px', textAlign: 'right' }}>Last Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {agents.map((agent, index) => (
                            <tr key={agent.name} className="leaderboard-row" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                                <td style={{ padding: '15px', fontWeight: 'bold', color: index === 0 ? '#ffd700' : index === 1 ? '#c0c0c0' : index === 2 ? '#cd7f32' : 'inherit' }}>
                                    #{index + 1}
                                </td>
                                <td style={{ padding: '15px', fontWeight: '500' }}>{agent.name}</td>
                                <td style={{ padding: '15px', textAlign: 'right', fontFamily: 'monospace', fontSize: '1.1rem' }}>
                                    ${agent.equity.toFixed(2)}
                                </td>
                                <td style={{ padding: '15px', textAlign: 'right', color: agent.roi >= 0 ? '#00c853' : '#d50000', fontWeight: 'bold' }}>
                                    {agent.roi.toFixed(2)}%
                                </td>
                                <td style={{ padding: '15px', textAlign: 'right', fontFamily: 'monospace' }}>
                                    ${agent.cash !== undefined ? agent.cash.toFixed(2) : '0.00'}
                                </td>
                                <td style={{ padding: '15px', textAlign: 'right', fontFamily: 'monospace', color: '#00c853', fontWeight: 'bold' }}>
                                    ${agent.cashed_out !== undefined ? agent.cashed_out.toFixed(2) : '0.00'}
                                </td>
                                {/* Portfolio Columns */}
                                <td style={{ padding: '15px', textAlign: 'right', fontFamily: 'monospace', color: '#ffab00' }}>
                                    ${agent.total_fees !== undefined ? agent.total_fees.toFixed(2) : '0.00'}
                                </td>
                                <td style={{ padding: '15px', textAlign: 'right', fontFamily: 'monospace' }}>
                                    {agent.portfolio?.BTC?.toFixed(4) || '0.000'}
                                </td>
                                <td style={{ padding: '15px', textAlign: 'right', fontFamily: 'monospace' }}>
                                    {agent.portfolio?.ETH?.toFixed(4) || '0.000'}
                                </td>
                                <td style={{ padding: '15px', textAlign: 'right', fontFamily: 'monospace' }}>
                                    {agent.portfolio?.SOL?.toFixed(4) || '0.000'}
                                </td>
                                <td style={{ padding: '15px', textAlign: 'right', fontFamily: 'monospace' }}>
                                    {agent.portfolio?.XRP?.toFixed(4) || '0.000'}
                                </td>
                                <td style={{ padding: '15px', textAlign: 'right', fontFamily: 'monospace' }}>
                                    {agent.portfolio?.BNB?.toFixed(4) || '0.000'}
                                </td>
                                <td style={{ padding: '15px', textAlign: 'right', fontFamily: 'monospace' }}>
                                    {agent.portfolio?.ZEC?.toFixed(4) || '0.000'}
                                </td>
                                <td style={{ padding: '15px', textAlign: 'right', fontFamily: 'monospace' }}>
                                    {agent.portfolio?.DOGE?.toFixed(4) || '0.000'}
                                </td>
                                <td style={{ padding: '15px', textAlign: 'right', fontFamily: 'monospace' }}>
                                    {agent.portfolio?.TRX?.toFixed(4) || '0.000'}
                                </td>
                                <td style={{ padding: '15px', textAlign: 'right', fontFamily: 'monospace' }}>
                                    {agent.portfolio?.SUI?.toFixed(4) || '0.000'}
                                </td>
                                <td style={{ padding: '15px', textAlign: 'right', fontFamily: 'monospace' }}>
                                    {agent.portfolio?.LINK?.toFixed(4) || '0.000'}
                                </td>

                                <td style={{ padding: '15px', textAlign: 'right', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                                    {agent.last_decision}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                {agents.length === 0 && <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>Waiting for market data...</div>}
            </div>
        </div>
    );
};

export default LeaderboardPage;
