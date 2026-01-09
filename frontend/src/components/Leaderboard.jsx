const Leaderboard = ({ agents }) => {
    return (
        <div style={{ height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <h3 style={{ margin: '0 0 10px 0', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>LEADERBOARD</h3>
            <div style={{ flex: 1, overflowY: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                        <tr style={{ textAlign: 'left', color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                            <th style={{ padding: '5px' }}>AGENT</th>
                            <th style={{ padding: '5px', textAlign: 'right' }}>EQUITY</th>
                            <th style={{ padding: '5px', textAlign: 'right' }}>PROFIT ($)</th>
                            <th style={{ padding: '5px', textAlign: 'right' }}>ROI</th>
                        </tr>
                    </thead>
                    <tbody>
                        {agents && agents.map(agent => (
                            <tr key={agent.name} style={{ borderBottom: '1px solid var(--border-color)' }}>
                                <td style={{ padding: '8px 5px', fontWeight: 'bold', fontSize: '0.85rem' }}>{agent.name}</td>

                                <td style={{ padding: '8px 5px', textAlign: 'right' }}>${agent.equity.toFixed(2)}</td>
                                <td style={{ padding: '8px 5px', textAlign: 'right', color: (agent.equity - 100) >= 0 ? '#00c853' : '#d50000', fontWeight: 'bold' }}>
                                    {(agent.equity - 100) > 0 ? '+' : ''}${(agent.equity - 100).toFixed(2)}
                                </td>
                                <td style={{ padding: '8px 5px', textAlign: 'right', color: agent.roi >= 0 ? '#00c853' : '#d50000', fontWeight: 'bold' }}>
                                    {agent.roi > 0 ? '+' : ''}{agent.roi.toFixed(2)}%
                                </td>
                            </tr>
                        ))}
                        {agents.length === 0 && (
                            <tr>
                                <td colSpan="4" style={{ textAlign: 'center', padding: '20px', color: 'var(--text-secondary)' }}>
                                    No agents deployed.
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default Leaderboard;
