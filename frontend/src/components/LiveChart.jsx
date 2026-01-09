import { ResponsiveContainer, LineChart, XAxis, YAxis, Tooltip, CartesianGrid, Line, ReferenceLine, Legend } from 'recharts';

const LiveChart = ({ data, agents }) => {
    // Generate distinct colors for agents (Neon/Bright for Dark Mode)
    const colors = ['#00ff9d', '#ff3fac', '#00bcd4', '#ff9800', '#d500f9', '#2962ff'];

    // Debug log to ensure data is flowing
    // console.log("LiveChart Data:", data.length, "Agents:", agents.map(a => a.name));

    return (
        <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
            <h3 style={{ margin: '0 0 10px 0', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>AGENT EQUITY COMPARISON</h3>
            <div style={{ flex: 1, minHeight: '300px', position: 'relative' }}>
                <div style={{ position: 'absolute', top: 5, right: 5, zIndex: 10, fontSize: '10px', color: '#aaa', background: 'rgba(0,0,0,0.5)', padding: '2px 5px' }}>
                    DEBUG: Agents: {agents.length} | Data: {data.length}
                </div>
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#2a2d50" vertical={false} opacity={0.5} />

                        {/* X Axis */}
                        <XAxis
                            dataKey="time"
                            type="number"
                            domain={['dataMin', 'dataMax']}
                            tickFormatter={(unix) => new Date(unix * 1000).toLocaleTimeString()}
                            stroke="#2a2d50"
                            fontSize={10}
                            tick={{ fill: '#a0a5cc' }}
                        />

                        {/* Left Axis: Agent Equity (Highlight) */}
                        <YAxis
                            yAxisId="left"
                            orientation="left"
                            domain={['auto', 'auto']}
                            stroke="#2a2d50"
                            width={60}
                            fontSize={10}
                            tick={{ fill: '#a0a5cc' }}
                            tickFormatter={(val) => `$${val.toLocaleString()}`}
                        />

                        <Tooltip
                            contentStyle={{
                                backgroundColor: 'rgba(15, 16, 38, 0.95)',
                                borderColor: '#2a2d50',
                                color: '#fff',
                                boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
                                borderRadius: '8px'
                            }}
                            itemStyle={{ fontSize: '12px', padding: '0' }}
                            labelStyle={{ color: '#a0a5cc', marginBottom: '5px' }}
                            labelFormatter={(label) => new Date(label * 1000).toLocaleTimeString()}
                        />

                        <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />

                        {/* Baseline at 10000 */}
                        <ReferenceLine y={10000} yAxisId="left" stroke="#5c5f80" strokeDasharray="3 3" label={{ value: 'START ($10,000)', position: 'insideTopLeft', fill: '#5c5f80', fontSize: 10 }} />

                        {/* Agent Lines */}
                        {agents.map((agent, index) => {
                            // Ensure we have a valid color
                            const color = colors[index % colors.length];
                            // Debug: Log what we are trying to render
                            // console.log(`Rendering Line for ${agent.name} with color ${color}`);

                            return (
                                <Line
                                    key={agent.name}
                                    yAxisId="left"
                                    type="linear"
                                    dataKey={agent.name}
                                    stroke={color}
                                    strokeWidth={3}
                                    dot={false}
                                    activeDot={{ r: 6 }}
                                    name={agent.name}
                                    isAnimationActive={false}
                                    connectNulls={true}
                                />
                            );
                        })}
                    </LineChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};

export default LiveChart;
