import React, { useState, useEffect } from 'react';
import { api } from '../api';

const AgentDetailModal = ({ agent, onClose, logs }) => {
    const [activeTab, setActiveTab] = useState('activity');
    const [agentCode, setAgentCode] = useState(null);
    const [codeLoading, setCodeLoading] = useState(false);
    const [codeError, setCodeError] = useState(null);

    if (!agent) return null;

    // Filter logs for this agent
    const agentLogs = logs.filter(log =>
        log.agent === agent.name ||
        log.agent_id === agent.name ||
        (log.message && log.message.includes(agent.name))
    );

    const pnl = (agent.equity || 10000) - 10000;
    const roi = agent.roi || (pnl / 10000 * 100);
    const isProfit = roi >= 0;

    // Fetch agent code when switching to algorithm tab
    useEffect(() => {
        if (activeTab === 'algorithm' && !agentCode && !codeLoading) {
            setCodeLoading(true);
            setCodeError(null);

            api.get(`/agent_code/${agent.name}`)
                .then(res => {
                    setAgentCode(res.data.code);
                    setCodeLoading(false);
                })
                .catch(err => {
                    setCodeError(err.response?.data?.error || 'Failed to load code');
                    setCodeLoading(false);
                });
        }
    }, [activeTab, agent.name, agentCode, codeLoading]);

    return (
        <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100vw',
            height: '100vh',
            background: 'rgba(0, 0, 0, 0.8)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 2000
        }} onClick={onClose}>
            <div style={{
                width: '700px',
                maxHeight: '85vh',
                background: 'var(--bg-surface)',
                border: '1px solid var(--bg-border)',
                borderRadius: '16px',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                boxShadow: '0 20px 60px rgba(0,0,0,0.5)'
            }} onClick={e => e.stopPropagation()}>

                {/* Header */}
                <div style={{
                    padding: '24px',
                    borderBottom: '1px solid var(--bg-border)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center'
                }}>
                    <div>
                        <h2 style={{
                            margin: '0 0 4px 0',
                            color: 'var(--text-primary)',
                            fontSize: '1.25rem',
                            fontWeight: '700'
                        }}>{agent.name}</h2>
                        <span style={{
                            fontSize: '0.75rem',
                            color: 'var(--text-muted)',
                            textTransform: 'uppercase',
                            letterSpacing: '1px'
                        }}>AI Trading Agent</span>
                    </div>
                    <button onClick={onClose} style={{
                        background: 'var(--bg-elevated)',
                        border: '1px solid var(--bg-border)',
                        color: 'var(--text-muted)',
                        width: '32px',
                        height: '32px',
                        borderRadius: '8px',
                        cursor: 'pointer',
                        fontSize: '1.25rem',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        transition: 'all 0.2s'
                    }}
                    onMouseEnter={(e) => {
                        e.currentTarget.style.background = 'var(--loss)';
                        e.currentTarget.style.color = 'var(--text-primary)';
                        e.currentTarget.style.borderColor = 'var(--loss)';
                    }}
                    onMouseLeave={(e) => {
                        e.currentTarget.style.background = 'var(--bg-elevated)';
                        e.currentTarget.style.color = 'var(--text-muted)';
                        e.currentTarget.style.borderColor = 'var(--bg-border)';
                    }}>
                        ×
                    </button>
                </div>

                {/* Stats */}
                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(4, 1fr)',
                    gap: '1px',
                    background: 'var(--bg-border)'
                }}>
                    <div style={{
                        background: 'var(--bg-surface)',
                        padding: '20px',
                        textAlign: 'center'
                    }}>
                        <div style={{
                            fontSize: '0.7rem',
                            color: 'var(--text-muted)',
                            marginBottom: '6px',
                            textTransform: 'uppercase',
                            letterSpacing: '0.5px'
                        }}>Equity</div>
                        <div style={{
                            fontSize: '1.25rem',
                            fontWeight: '700',
                            color: 'var(--text-primary)'
                        }}>
                            ${(agent.equity || 10000).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                        </div>
                    </div>
                    <div style={{
                        background: 'var(--bg-surface)',
                        padding: '20px',
                        textAlign: 'center'
                    }}>
                        <div style={{
                            fontSize: '0.7rem',
                            color: 'var(--text-muted)',
                            marginBottom: '6px',
                            textTransform: 'uppercase',
                            letterSpacing: '0.5px'
                        }}>P&L</div>
                        <div style={{
                            fontSize: '1.25rem',
                            fontWeight: '700',
                            color: isProfit ? 'var(--profit)' : 'var(--loss)'
                        }}>
                            {isProfit ? '+' : ''}${pnl.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                        </div>
                    </div>
                    <div style={{
                        background: 'var(--bg-surface)',
                        padding: '20px',
                        textAlign: 'center'
                    }}>
                        <div style={{
                            fontSize: '0.7rem',
                            color: 'var(--text-muted)',
                            marginBottom: '6px',
                            textTransform: 'uppercase',
                            letterSpacing: '0.5px'
                        }}>ROI</div>
                        <div style={{
                            fontSize: '1.25rem',
                            fontWeight: '700',
                            color: isProfit ? 'var(--profit)' : 'var(--loss)'
                        }}>
                            {isProfit ? '+' : ''}{roi.toFixed(2)}%
                        </div>
                    </div>
                    <div style={{
                        background: 'var(--bg-surface)',
                        padding: '20px',
                        textAlign: 'center'
                    }}>
                        <div style={{
                            fontSize: '0.7rem',
                            color: 'var(--text-muted)',
                            marginBottom: '6px',
                            textTransform: 'uppercase',
                            letterSpacing: '0.5px'
                        }}>Trades</div>
                        <div style={{
                            fontSize: '1.25rem',
                            fontWeight: '700',
                            color: 'var(--text-primary)'
                        }}>
                            {agent.trades || 0}
                        </div>
                    </div>
                </div>

                {/* Tabs */}
                <div style={{
                    display: 'flex',
                    borderBottom: '1px solid var(--bg-border)',
                    background: 'rgba(0,0,0,0.2)'
                }}>
                    <button
                        onClick={() => setActiveTab('activity')}
                        style={{
                            flex: 1,
                            padding: '14px 20px',
                            background: 'transparent',
                            border: 'none',
                            borderBottom: activeTab === 'activity' ? '2px solid var(--accent-primary)' : '2px solid transparent',
                            color: activeTab === 'activity' ? 'var(--text-primary)' : 'var(--text-muted)',
                            fontSize: '0.8rem',
                            fontWeight: '600',
                            cursor: 'pointer',
                            transition: 'all 0.2s',
                            textTransform: 'uppercase',
                            letterSpacing: '0.5px'
                        }}
                    >
                        Activity Log
                    </button>
                    <button
                        onClick={() => setActiveTab('algorithm')}
                        style={{
                            flex: 1,
                            padding: '14px 20px',
                            background: 'transparent',
                            border: 'none',
                            borderBottom: activeTab === 'algorithm' ? '2px solid var(--accent-primary)' : '2px solid transparent',
                            color: activeTab === 'algorithm' ? 'var(--text-primary)' : 'var(--text-muted)',
                            fontSize: '0.8rem',
                            fontWeight: '600',
                            cursor: 'pointer',
                            transition: 'all 0.2s',
                            textTransform: 'uppercase',
                            letterSpacing: '0.5px'
                        }}
                    >
                        Algorithm
                    </button>
                </div>

                {/* Tab Content */}
                <div style={{ flex: 1, overflowY: 'auto', padding: '0' }}>
                    {activeTab === 'activity' && (
                        <>
                            {agentLogs.length === 0 ? (
                                <div style={{
                                    padding: '40px 20px',
                                    textAlign: 'center',
                                    color: 'var(--text-subtle)',
                                    fontSize: '0.875rem'
                                }}>
                                    No activity recorded yet.
                                </div>
                            ) : (
                                <div style={{ display: 'flex', flexDirection: 'column' }}>
                                    {agentLogs.slice(0, 20).map((log, i) => (
                                        <div key={i} style={{
                                            padding: '14px 24px',
                                            borderBottom: '1px solid var(--bg-border)',
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '12px'
                                        }}>
                                            {log.action && (
                                                <span style={{
                                                    padding: '4px 8px',
                                                    borderRadius: '4px',
                                                    fontSize: '0.65rem',
                                                    fontWeight: '700',
                                                    letterSpacing: '0.5px',
                                                    background: log.action === 'BUY' ? 'var(--profit)' : 'var(--loss)',
                                                    color: log.action === 'BUY' ? 'var(--bg-base)' : 'var(--text-primary)'
                                                }}>
                                                    {log.action}
                                                </span>
                                            )}
                                            <div style={{ flex: 1 }}>
                                                <span style={{
                                                    color: 'var(--text-secondary)',
                                                    fontSize: '0.85rem'
                                                }}>
                                                    {log.symbol || log.message || 'Trade executed'}
                                                </span>
                                                {log.price && (
                                                    <span style={{
                                                        marginLeft: '8px',
                                                        color: 'var(--text-muted)',
                                                        fontSize: '0.8rem'
                                                    }}>
                                                        @ ${log.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                                    </span>
                                                )}
                                            </div>
                                            <span style={{
                                                color: 'var(--text-subtle)',
                                                fontSize: '0.75rem'
                                            }}>
                                                {log.timestamp ? new Date(log.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </>
                    )}

                    {activeTab === 'algorithm' && (
                        <div style={{ padding: '0' }}>
                            {codeLoading && (
                                <div style={{
                                    padding: '40px 20px',
                                    textAlign: 'center',
                                    color: 'var(--text-muted)',
                                    fontSize: '0.875rem'
                                }}>
                                    Loading algorithm...
                                </div>
                            )}

                            {codeError && (
                                <div style={{
                                    padding: '40px 20px',
                                    textAlign: 'center',
                                    color: 'var(--loss)',
                                    fontSize: '0.875rem'
                                }}>
                                    {codeError}
                                </div>
                            )}

                            {agentCode && !codeLoading && (
                                <div style={{
                                    position: 'relative'
                                }}>
                                    {/* Code header */}
                                    <div style={{
                                        padding: '12px 20px',
                                        background: 'var(--bg-elevated)',
                                        borderBottom: '1px solid var(--bg-border)',
                                        display: 'flex',
                                        justifyContent: 'space-between',
                                        alignItems: 'center'
                                    }}>
                                        <span style={{
                                            fontSize: '0.75rem',
                                            color: 'var(--text-muted)',
                                            fontFamily: 'monospace'
                                        }}>
                                            {agent.name}.py
                                        </span>
                                        <button
                                            onClick={() => {
                                                navigator.clipboard.writeText(agentCode);
                                            }}
                                            style={{
                                                background: 'var(--bg-surface)',
                                                border: '1px solid var(--bg-border)',
                                                color: 'var(--text-muted)',
                                                padding: '4px 10px',
                                                borderRadius: '4px',
                                                fontSize: '0.7rem',
                                                cursor: 'pointer',
                                                transition: 'all 0.2s'
                                            }}
                                            onMouseEnter={(e) => {
                                                e.currentTarget.style.background = 'var(--accent-primary)';
                                                e.currentTarget.style.color = 'var(--bg-base)';
                                            }}
                                            onMouseLeave={(e) => {
                                                e.currentTarget.style.background = 'var(--bg-surface)';
                                                e.currentTarget.style.color = 'var(--text-muted)';
                                            }}
                                        >
                                            Copy
                                        </button>
                                    </div>

                                    {/* Code content */}
                                    <pre style={{
                                        margin: 0,
                                        padding: '16px 20px',
                                        background: 'var(--bg-base)',
                                        color: 'var(--text-secondary)',
                                        fontSize: '0.75rem',
                                        lineHeight: '1.6',
                                        fontFamily: "'Fira Code', 'Monaco', 'Consolas', monospace",
                                        overflow: 'auto',
                                        maxHeight: '400px',
                                        whiteSpace: 'pre',
                                        tabSize: 4
                                    }}>
                                        <code>{agentCode}</code>
                                    </pre>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default AgentDetailModal;
