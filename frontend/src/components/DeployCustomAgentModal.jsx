import React, { useState } from 'react';
import { api } from '../api';

const DeployCustomAgentModal = ({ onClose, onSuccess }) => {
    const [name, setName] = useState('');
    const [code, setCode] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState(null);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError(null);

        if (!name.trim()) {
            setError('Agent name is required');
            return;
        }

        if (!code.trim()) {
            setError('Agent strategy code is required');
            return;
        }

        setIsSubmitting(true);

        try {
            const res = await api.post('/deploy_custom_agent', {
                name: name.trim(),
                code: code.trim()
            });

            if (res.data.success) {
                onSuccess(res.data.name);
                onClose();
            } else {
                setError(res.data.error || 'Failed to deploy agent');
            }
        } catch (err) {
            setError(err.response?.data?.error || err.message || 'An error occurred during deployment');
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="modal-backdrop" onClick={onClose} style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            display: 'flex', justifyContent: 'center', alignItems: 'center',
            zIndex: 1000, backdropFilter: 'blur(4px)'
        }}>
            <div className="modal-content glass-panel" onClick={e => e.stopPropagation()} style={{
                width: '600px', maxWidth: '90%', maxHeight: '90vh',
                display: 'flex', flexDirection: 'column',
                padding: '24px', position: 'relative'
            }}>
                <button
                    onClick={onClose}
                    style={{
                        position: 'absolute', top: '16px', right: '16px',
                        background: 'transparent', border: 'none',
                        color: 'var(--text-muted)', cursor: 'pointer',
                        fontSize: '1.5rem', lineHeight: 1
                    }}
                >×</button>

                <h2 style={{ marginTop: 0, marginBottom: '20px', color: 'var(--text-primary)' }}>
                    Deploy Custom Agent
                </h2>

                <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px', flex: 1, minHeight: 0 }}>

                    {error && (
                        <div style={{
                            padding: '12px', background: 'rgba(239, 68, 68, 0.1)',
                            borderLeft: '4px solid #ef4444', color: '#fca5a5',
                            fontSize: '0.875rem', borderRadius: '4px'
                        }}>
                            {error}
                        </div>
                    )}

                    <div>
                        <label style={{ display: 'block', marginBottom: '8px', fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                            Agent Name
                        </label>
                        <input
                            type="text"
                            value={name}
                            onChange={e => setName(e.target.value)}
                            placeholder="e.g. MyAwesomeStrategy"
                            style={{
                                width: '100%', padding: '10px 12px',
                                background: 'rgba(17, 24, 39, 0.7)',
                                border: '1px solid rgba(255, 255, 255, 0.1)',
                                borderRadius: '6px', color: 'var(--text-primary)',
                                outline: 'none'
                            }}
                        />
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                            Will be automatically prefixed with "Agent_" if not provided.
                        </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
                        <label style={{ display: 'block', marginBottom: '8px', fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                            Python Code (execute_strategy function)
                        </label>
                        <textarea
                            value={code}
                            onChange={e => setCode(e.target.value)}
                            placeholder="def execute_strategy(market_data, tick, cash_balance, portfolio, ...):&#10;    # Your strategy logic here&#10;    return ('HOLD', None, 0)"
                            style={{
                                width: '100%', flex: 1, minHeight: '200px',
                                padding: '12px', background: 'rgba(17, 24, 39, 0.7)',
                                border: '1px solid rgba(255, 255, 255, 0.1)',
                                borderRadius: '6px', color: 'var(--text-primary)',
                                fontFamily: 'monospace', outline: 'none',
                                resize: 'vertical'
                            }}
                            spellCheck={false}
                        />
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '8px' }}>
                        <button
                            type="button"
                            onClick={onClose}
                            style={{
                                padding: '10px 16px', background: 'transparent',
                                border: '1px solid rgba(255, 255, 255, 0.2)',
                                color: 'var(--text-primary)', borderRadius: '6px',
                                cursor: 'pointer', fontWeight: 600
                            }}
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={isSubmitting}
                            style={{
                                padding: '10px 24px', background: 'var(--accent-primary)',
                                border: 'none', color: 'var(--bg-base)',
                                borderRadius: '6px', cursor: isSubmitting ? 'not-allowed' : 'pointer',
                                fontWeight: 700, opacity: isSubmitting ? 0.7 : 1
                            }}
                        >
                            {isSubmitting ? 'Deploying...' : 'Deploy to Arena'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default DeployCustomAgentModal;
