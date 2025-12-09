import { useState } from 'react';
import { api } from '../api';

const ControlPanel = () => {

    // Handlers
    const handleStop = async () => {
        await api.post('/stop_arena');
        alert('Arena Stopped');
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <h3 style={{ margin: '0 0 10px 0', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>CONTROL PANEL</h3>

            <div style={{ display: 'flex', gap: '10px' }}>
                <button className="btn btn-danger" onClick={handleStop} style={{ flex: 1 }}>STOP TRADING</button>
            </div>

            <div style={{ marginTop: '10px', paddingTop: '10px', borderTop: '1px solid var(--border-color)' }}>
                <button
                    className="btn"
                    style={{ width: '100%', background: 'rgba(213, 0, 0, 0.2)', border: '1px solid #d50000', color: '#ff8a80' }}
                    onClick={async () => {
                        if (confirm('HARD RESET: Clear all progress and restart?')) {
                            await api.post('/reset_arena');
                            window.location.reload();
                        }
                    }}
                >
                    ⚠️ HARD RESET ARENA
                </button>
            </div>
        </div>
    );
};

export default ControlPanel;
