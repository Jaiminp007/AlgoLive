import { useState, useEffect, useRef } from 'react';
import { api } from '../api';

const AgentSelection = ({ onStart }) => {
    const [models, setModels] = useState({});
    const [selectedModels, setSelectedModels] = useState([]);
    const [isGenerating, setIsGenerating] = useState(false);
    const [generationLogs, setGenerationLogs] = useState([]);
    const [error, setError] = useState(null);
    const [failedAgents, setFailedAgents] = useState([]); // [{index, name, originalModel}]
    const [successfulAgents, setSuccessfulAgents] = useState([]); // names of deployed agents
    const logRef = useRef(null);
    const [showPasteModal, setShowPasteModal] = useState(false);
    const [customName, setCustomName] = useState('Agent_custom_');
    const [customCode, setCustomCode] = useState('');
    const [customError, setCustomError] = useState(null);
    const [customDeploying, setCustomDeploying] = useState(false);

    useEffect(() => {
        console.log("AgentSelection: Fetching models...");
        api.get('/available_models')
            .then(res => {
                console.log("AgentSelection: Models fetched:", res.data);
                if (res.data && Object.keys(res.data).length > 0) {
                    setModels(res.data);
                } else {
                    setError("No models found in response.");
                }
            })
            .catch(err => {
                console.error("Failed to load models:", err);
                setError(err.message || "Failed to load models.");
            });
    }, []);

    // Auto-scroll logs
    useEffect(() => {
        if (logRef.current) {
            logRef.current.scrollTop = logRef.current.scrollHeight;
        }
    }, [generationLogs]);

    const handleSelectChange = (e) => {
        const model = e.target.value;
        if (!model) return;
        if (selectedModels.includes(model)) return;
        if (selectedModels.includes(model)) return;
        // Limit removed per user request
        setSelectedModels(prev => [...prev, model]);
        e.target.value = "";
    };

    const removeModel = (modelToRemove) => {
        setSelectedModels(prev => prev.filter(m => m !== modelToRemove));
    };

    const generateAgent = async (model, index) => {
        const safeModelName = model.replace(/[^a-zA-Z0-9]/g, '_');
        const agentName = `Agent_${index + 1}_${safeModelName.slice(0, 20)}`;

        setGenerationLogs(prev => [...prev, `Generating ${agentName} using ${model}...`]);

        try {
            const genRes = await api.post('/generate_agent', { name: agentName, model: model });

            if (genRes.data.success) {
                setGenerationLogs(prev => [...prev, `✅ Generated ${agentName}`]);
                setGenerationLogs(prev => [...prev, `Deploying ${agentName}...`]);
                await api.post('/deploy_agent', { name: agentName });
                setGenerationLogs(prev => [...prev, `🚀 Deployed ${agentName}`]);
                return { success: true, name: agentName };
            } else {
                setGenerationLogs(prev => [...prev, `❌ Failed: ${genRes.data.error}`]);
                return { success: false, name: agentName, error: genRes.data.error };
            }
        } catch (err) {
            setGenerationLogs(prev => [...prev, `❌ Error: ${err.message}`]);
            return { success: false, name: agentName, error: err.message };
        }
    };

    const handleStart = async () => {
        if (selectedModels.length === 0) return;
        setIsGenerating(true);
        setGenerationLogs(["Starting generation process..."]);
        setFailedAgents([]);
        setSuccessfulAgents([]);

        const newFailed = [];
        const newSuccessful = [];

        for (let i = 0; i < selectedModels.length; i++) {
            const model = selectedModels[i];
            const result = await generateAgent(model, i);

            if (result.success) {
                newSuccessful.push(result.name);
            } else {
                newFailed.push({ index: i, name: result.name, originalModel: model });
            }
        }

        setSuccessfulAgents(newSuccessful);
        setFailedAgents(newFailed);

        if (newFailed.length === 0 && newSuccessful.length > 0) {
            // All succeeded, start market
            setGenerationLogs(prev => [...prev, "Starting Market..."]);
            await api.post('/start_arena');
            onStart();
        } else if (newFailed.length > 0) {
            setGenerationLogs(prev => [...prev, `⚠️ ${newFailed.length} agent(s) failed. Select replacement models below.`]);
        }
    };

    const handleRetry = async (failedIndex, newModel) => {
        setGenerationLogs(prev => [...prev, `🔄 Retrying with ${newModel}...`]);

        const result = await generateAgent(newModel, failedIndex);

        if (result.success) {
            const updatedFailed = failedAgents.filter(f => f.index !== failedIndex);
            setSuccessfulAgents(prev => [...prev, result.name]);
            setFailedAgents(updatedFailed);
            setGenerationLogs(prev => [...prev, `✅ Retry successful!`]);

            // If all failures are now resolved, auto-start the market
            if (updatedFailed.length === 0) {
                setGenerationLogs(prev => [...prev, `🎉 All agents ready! Starting Market...`]);
                await api.post('/start_arena');
                onStart();
            }
        } else {
            setGenerationLogs(prev => [...prev, `❌ Retry failed. Try a different model.`]);
        }
    };

    const handleFinish = async () => {
        if (successfulAgents.length > 0) {
            setGenerationLogs(prev => [...prev, "Starting Market with successful agents..."]);
            await api.post('/start_arena');
            onStart();
        }
    };

    const handleDeployCustom = async () => {
        if (!customName.trim() || !customCode.trim()) return;
        setCustomDeploying(true);
        setCustomError(null);
        try {
            const res = await api.post('/deploy_custom_agent', { name: customName.trim(), code: customCode.trim() });
            if (res.data.success) {
                const deployedName = res.data.name;
                setSuccessfulAgents(prev => [...prev, deployedName]);
                setGenerationLogs(prev => [...prev, `Deployed ${deployedName} (custom code)`]);
                setShowPasteModal(false);
                setCustomCode('');
                setCustomName('Agent_custom_');
            } else {
                setCustomError(res.data.error || 'Unknown error');
            }
        } catch (err) {
            const msg = err.response?.data?.error || err.message;
            setCustomError(msg);
        } finally {
            setCustomDeploying(false);
        }
    };

    const allModelsFlat = Object.values(models).flat();

    return (
        <div className="glass-panel" style={{ padding: '20px', maxWidth: '800px', margin: '40px auto', color: 'var(--text-primary)' }}>
            <h2 style={{ borderBottom: '1px solid var(--border)', paddingBottom: '10px' }}>Select Agents (Unlimited)</h2>

            {!isGenerating ? (
                <>
                    {error && (
                        <div style={{ padding: '10px', background: 'rgba(213, 0, 0, 0.2)', border: '1px solid #d50000', color: '#ff5555', marginBottom: '15px' }}>
                            Error: {error} <br />
                            <button onClick={() => window.location.reload()} style={{ marginTop: '5px', padding: '4px 8px' }}>Retry</button>
                        </div>
                    )}

                    <div style={{ marginBottom: '20px' }}>
                        <label style={{ display: 'block', marginBottom: '5px', color: 'var(--text-secondary)' }}>Add Agent from Provider:</label>
                        <select onChange={handleSelectChange}
                            style={{ width: '100%', padding: '10px', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '4px' }}
                            defaultValue="">
                            <option value="" disabled>Select a model...</option>
                            {Object.entries(models).map(([provider, providerModels]) => (
                                <optgroup key={provider} label={provider}>
                                    {providerModels.map(model => (
                                        <option key={model} value={model} disabled={selectedModels.includes(model)}>
                                            {model.split('/').pop()} ({model})
                                        </option>
                                    ))}
                                </optgroup>
                            ))}
                        </select>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '5px' }}>
                            {Object.keys(models).length === 0 ? "Loading models..." : `${allModelsFlat.length} models available`}
                        </div>
                    </div>

                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', minHeight: '100px', background: 'rgba(0,0,0,0.2)', padding: '10px', borderRadius: '4px' }}>
                        {selectedModels.length === 0 && <div style={{ color: 'var(--text-secondary)', alignSelf: 'center', width: '100%', textAlign: 'center' }}>No agents selected</div>}
                        {selectedModels.map((model, idx) => (
                            <div key={idx} style={{ background: 'var(--accent-blue)', color: '#fff', padding: '5px 10px', borderRadius: '20px', display: 'flex', alignItems: 'center', gap: '8px', border: '1px solid rgba(255,255,255,0.2)' }}>
                                <span>{model.split('/').pop()}</span>
                                <button onClick={() => removeModel(model)} style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', fontWeight: 'bold', fontSize: '1rem', lineHeight: 1 }}>×</button>
                            </div>
                        ))}
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '20px', borderTop: '1px solid var(--border)', paddingTop: '20px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                            <span>Selected: {selectedModels.length}</span>
                            <button
                                onClick={async () => {
                                    if (window.confirm('Are you sure you want to clear ALL data? This will delete all agents, trades, and chart history.')) {
                                        try {
                                            await api.post('/clear_all_data');
                                            alert('All data cleared! Page will reload.');
                                            window.location.reload();
                                        } catch (err) {
                                            alert('Failed to clear data: ' + err.message);
                                        }
                                    }
                                }}
                                style={{
                                    padding: '6px 12px',
                                    background: 'rgba(200, 50, 50, 0.3)',
                                    border: '1px solid #ff5555',
                                    color: '#ff5555',
                                    borderRadius: '4px',
                                    cursor: 'pointer',
                                    fontSize: '0.8rem'
                                }}
                            >
                                CLEAR ALL DATA
                            </button>
                            <button
                                onClick={() => { setShowPasteModal(true); setCustomError(null); }}
                                style={{
                                    padding: '6px 12px',
                                    background: 'rgba(255, 160, 0, 0.15)',
                                    border: '1px solid #ffa000',
                                    color: '#ffa000',
                                    borderRadius: '4px',
                                    cursor: 'pointer',
                                    fontSize: '0.8rem'
                                }}
                            >
                                PASTE CODE
                            </button>
                        </div>
                        <button className="cyber-button" onClick={handleStart} disabled={selectedModels.length === 0} style={{ opacity: selectedModels.length === 0 ? 0.5 : 1 }}>
                            START MARKET
                        </button>
                    </div>
                </>
            ) : (
                <div style={{ marginTop: '20px' }}>
                    <div ref={logRef} style={{ background: '#000', padding: '15px', borderRadius: '4px', height: '250px', overflowY: 'auto', fontFamily: 'monospace', fontSize: '0.85rem' }}>
                        {generationLogs.map((log, i) => (
                            <div key={i} style={{ marginBottom: '5px', color: log.includes('❌') ? '#ff5555' : log.includes('✅') ? '#55ff55' : log.includes('⚠️') ? '#ffaa00' : '#ccc' }}>
                                &gt; {log}
                            </div>
                        ))}
                    </div>

                    {/* Failed agents replacement UI */}
                    {failedAgents.length > 0 && (
                        <div style={{ marginTop: '15px', padding: '15px', background: 'rgba(255, 170, 0, 0.1)', border: '1px solid #ffaa00', borderRadius: '4px' }}>
                            <h4 style={{ margin: '0 0 10px', color: '#ffaa00' }}>⚠️ Failed Agents - Select Replacement Models</h4>
                            {failedAgents.map(failed => (
                                <div key={failed.index} style={{ display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '10px' }}>
                                    <span style={{ flex: 1, color: '#ff5555' }}>Agent {failed.index + 1}: {failed.originalModel.split('/').pop()}</span>
                                    <select
                                        onChange={(e) => { if (e.target.value) handleRetry(failed.index, e.target.value); }}
                                        style={{ padding: '8px', background: 'rgba(0,0,0,0.5)', border: '1px solid var(--border)', color: '#fff', borderRadius: '4px', flex: 1 }}
                                        defaultValue="">
                                        <option value="">Select replacement...</option>
                                        {allModelsFlat.filter(m => m !== failed.originalModel).map(model => (
                                            <option key={model} value={model}>{model.split('/').pop()}</option>
                                        ))}
                                    </select>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Finish button when some succeeded */}
                    {successfulAgents.length > 0 && (
                        <div style={{ marginTop: '15px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ color: '#55ff55' }}>✅ {successfulAgents.length} agent(s) ready</span>
                            <button className="cyber-button" onClick={handleFinish}>
                                START WITH {successfulAgents.length} AGENT{successfulAgents.length > 1 ? 'S' : ''}
                            </button>
                        </div>
                    )}
                </div>
            )}
            {showPasteModal && (
                <div style={{
                    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                    background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
                }}
                    onClick={(e) => { if (e.target === e.currentTarget) setShowPasteModal(false); }}
                >
                    <div className="glass-panel" style={{ width: '500px', maxHeight: '90vh', padding: '24px', overflow: 'auto' }}>
                        <h3 style={{ margin: '0 0 16px', borderBottom: '1px solid var(--border)', paddingBottom: '10px' }}>Deploy Custom Algorithm</h3>

                        <label style={{ display: 'block', marginBottom: '4px', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Agent Name</label>
                        <input
                            type="text"
                            value={customName}
                            onChange={(e) => setCustomName(e.target.value)}
                            style={{
                                width: '100%', padding: '8px', marginBottom: '12px',
                                background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border)',
                                color: 'var(--text-primary)', borderRadius: '4px', boxSizing: 'border-box'
                            }}
                        />

                        <label style={{ display: 'block', marginBottom: '4px', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Strategy Code</label>
                        <textarea
                            value={customCode}
                            onChange={(e) => setCustomCode(e.target.value)}
                            placeholder={`def execute_strategy(market_data, tick, cash_balance, portfolio, market_state=None, agent_state=None):\n    # Your strategy here\n    return ("HOLD", None, 0)`}
                            style={{
                                width: '100%', height: '400px', padding: '10px', marginBottom: '12px',
                                background: 'rgba(0,0,0,0.5)', border: '1px solid var(--border)',
                                color: '#e0e0e0', borderRadius: '4px', fontFamily: 'monospace', fontSize: '0.8rem',
                                resize: 'vertical', boxSizing: 'border-box'
                            }}
                        />

                        {customError && (
                            <div style={{
                                padding: '10px', marginBottom: '12px',
                                background: 'rgba(213,0,0,0.2)', border: '1px solid #ff5555',
                                color: '#ff5555', borderRadius: '4px', fontSize: '0.85rem', wordBreak: 'break-word'
                            }}>
                                {customError}
                            </div>
                        )}

                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                            <button
                                onClick={() => setShowPasteModal(false)}
                                style={{
                                    padding: '8px 16px', background: 'transparent',
                                    border: '1px solid var(--border)', color: 'var(--text-secondary)',
                                    borderRadius: '4px', cursor: 'pointer'
                                }}
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleDeployCustom}
                                disabled={customDeploying || !customCode.trim()}
                                className="cyber-button"
                                style={{ opacity: customDeploying || !customCode.trim() ? 0.5 : 1 }}
                            >
                                {customDeploying ? 'Deploying...' : 'Deploy'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default AgentSelection;
