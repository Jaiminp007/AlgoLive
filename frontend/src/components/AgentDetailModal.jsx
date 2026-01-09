import React from 'react';

const AgentDetailModal = ({ agent, onClose, logs }) => {
    if (!agent) return null;

    // Filter logs for this agent
    const agentLogs = logs.filter(log => log.agent_id === agent.name || log.message.includes(agent.name));

    return (
        <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100vw',
            height: '100vh',
            background: 'rgba(0, 0, 0, 0.7)',
            backdropFilter: 'blur(5px)',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 2000
        }} onClick={onClose}>
            <div style={{
                width: '600px',
                maxHeight: '80vh',
                background: '#151632', // Dark panel color
                border: '1px solid #2a2d50',
                borderRadius: '12px',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                boxShadow: '0 10px 40px rgba(0,0,0,0.5)'
            }} onClick={e => e.stopPropagation()}>

                {/* Header */}
                <div style={{ padding: '20px', borderBottom: '1px solid #2a2d50', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                        <h2 style={{ margin: 0, color: '#fff' }}>{agent.name}</h2>
                        <span style={{ fontSize: '0.8rem', color: '#a0a5cc' }}>AI TRADING AGENT</span>
                    </div>
                    <button onClick={onClose} style={{
                        background: 'transparent',
                        border: 'none',
                        color: '#a0a5cc',
                        fontSize: '1.5rem',
                        cursor: 'pointer'
                    }}>×</button>
                </div>

                {/* Stats */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1px', background: '#2a2d50' }}>
                    <div style={{ background: '#151632', padding: '20px', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.8rem', color: '#a0a5cc', marginBottom: '5px' }}>EQUITY</div>
                        <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: '#fff' }}>${agent.equity.toFixed(2)}</div>
                    </div>
                    <div style={{ background: '#151632', padding: '20px', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.8rem', color: '#a0a5cc', marginBottom: '5px' }}>PROFIT</div>
                        <div style={{
                            fontSize: '1.2rem',
                            fontWeight: 'bold',
                            color: (agent.equity - 100) >= 0 ? '#00c853' : '#d50000'
                        }}>
                            {(agent.equity - 100) > 0 ? '+' : ''}${(agent.equity - 100).toFixed(2)}
                        </div>
                    </div>
                    <div style={{ background: '#151632', padding: '20px', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.8rem', color: '#a0a5cc', marginBottom: '5px' }}>ROI</div>
                        <div style={{
                            fontSize: '1.2rem',
                            fontWeight: 'bold',
                            color: agent.roi >= 0 ? '#00c853' : '#d50000'
                        }}>
                            {agent.roi > 0 ? '+' : ''}{agent.roi.toFixed(2)}%
                        </div>
                    </div>
                </div>

                {/* Trade History */}
                <div style={{ flex: 1, overflowY: 'auto', padding: '0' }}>
                    <h3 style={{ padding: '15px 20px', margin: 0, fontSize: '0.9rem', color: '#a0a5cc', borderBottom: '1px solid #2a2d50', background: 'rgba(0,0,0,0.2)' }}>
                        ACTIVITY LOG
                    </h3>
                    {agentLogs.length === 0 ? (
                        <div style={{ padding: '20px', textAlign: 'center', color: '#5c5f80', fontStyle: 'italic' }}>No activity recorded yet.</div>
                    ) : (
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                            {agentLogs.map((log, i) => (
                                <div key={i} style={{
                                    padding: '12px 20px',
                                    borderBottom: '1px solid rgba(255,255,255,0.05)',
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    fontSize: '0.9rem'
                                }}>
                                    <span style={{ color: log.type === 'buy' ? '#00c853' : log.type === 'sell' ? '#d50000' : '#fff' }}>
                                        {log.message}
                                    </span>
                                    <span style={{ color: '#5c5f80', fontSize: '0.8rem' }}>
                                        {new Date(log.timestamp * 1000).toLocaleTimeString()}
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default AgentDetailModal;
