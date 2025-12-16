import { useState } from 'react';
import { api } from '../api';

const ControlPanel = () => {

    // Handlers
    const handleStop = async () => {
        await api.post('/stop_arena');
        alert('Arena Stopped');
    };

    const handleSoftReset = async () => {
        if (!window.confirm("RESET ARENA?\n\nThis will reset equity to $10k and clear charts/trades, but KEEP all agents.")) return;
        try {
            await api.post('/soft_reset_arena');
            // alert('Arena Reset Successfully');
        } catch (e) {
            alert('Reset Failed');
        }
    };

    const handleRebuild = async () => {
        if (!window.confirm("REBUILD ALGOS?\n\nThis will evaluate all agents and potentially Hot-Swap them with new code.")) return;
        try {
            await api.post('/rebuild_algos');
            alert('Rebuild Initiated in Background');
        } catch (e) {
            alert('Rebuild Failed');
        }
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <h3 style={{ margin: '0 0 10px 0', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>CONTROL PANEL</h3>
            <div style={{ padding: '10px', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                System Automated
            </div>

            <button onClick={handleRebuild} style={{
                background: 'rgba(0, 188, 212, 0.1)',
                border: '1px solid var(--accent-blue)',
                color: 'var(--accent-blue)',
                padding: '8px',
                borderRadius: '4px',
                cursor: 'pointer',
                fontWeight: 'bold',
                fontSize: '0.8rem',
                transition: 'all 0.2s'
            }}>
                REBUILD ALGOS
            </button>

            <button onClick={handleSoftReset} style={{
                background: 'rgba(255, 171, 0, 0.1)',
                border: '1px solid var(--accent-orange)',
                color: 'var(--accent-orange)',
                padding: '8px',
                borderRadius: '4px',
                cursor: 'pointer',
                fontWeight: 'bold',
                fontSize: '0.8rem',
                transition: 'all 0.2s'
            }}>
                RESET ARENA
            </button>
        </div>
    );
};

export default ControlPanel;
