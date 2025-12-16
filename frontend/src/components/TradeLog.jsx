const TradeLog = ({ logs }) => {
    return (
        <div style={{ flex: 1, overflowY: 'auto', fontSize: '0.85rem' }}>
            {logs.map((log, index) => (
                <div key={index} style={{
                    padding: '8px 0',
                    borderBottom: '1px solid var(--border-color)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px'
                }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span>
                            <span style={{ fontWeight: 'bold', color: log.action === 'BUY' ? '#00c853' : '#d50000' }}>
                                {log.action}
                            </span>{' '}
                            <span style={{ color: 'var(--text-primary)', fontWeight: '600' }}>{log.agent}</span>
                        </span>
                        <div style={{ textAlign: 'right' }}>
                            <span style={{ color: 'var(--text-secondary)' }}>
                                @ ${log.price.toLocaleString()}
                            </span>
                            {log.fee > 0 && (
                                <span style={{ marginLeft: '8px', fontSize: '0.75rem', color: '#ffab00' }}>
                                    (Fee: ${log.fee.toFixed(2)})
                                </span>
                            )}
                        </div>
                    </div>
                    {log.reason && (
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontStyle: 'italic', paddingLeft: '8px', borderLeft: '2px solid var(--border-color)' }}>
                            "{log.reason}"
                        </div>
                    )}
                </div>
            ))}
            {logs.length === 0 && (
                <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-secondary)' }}>
                    Waiting for trades...
                </div>
            )}
        </div>
    );
};

export default TradeLog;
