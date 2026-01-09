import React from 'react';
import { ResponsiveContainer, LineChart, XAxis, YAxis, Tooltip, CartesianGrid, Line, AreaChart, Area } from 'recharts';

const StockChart = ({ data, symbol, color = '#2962ff' }) => {
    // Determine min/max for better axis scaling
    const prices = data.map(d => d.price);
    const minPrice = Math.min(...prices) * 0.999;
    const maxPrice = Math.max(...prices) * 1.001;

    return (
        <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '5px' }}>
                <h3 style={{ margin: 0, fontSize: '0.85rem', color: color, display: 'flex', alignItems: 'center', gap: '5px' }}>
                    <span style={{
                        display: 'inline-block',
                        padding: '2px 6px',
                        borderRadius: '4px',
                        background: `${color}20`,
                        border: `1px solid ${color}40`,
                        fontSize: '0.7rem'
                    }}>{symbol}</span>
                </h3>
            </div>

            <div style={{ flex: 1, minHeight: '0', position: 'relative' }}>
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={data}>
                        <defs>
                            <linearGradient id={`gradient-${symbol}`} x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor={color} stopOpacity={0.3} />
                                <stop offset="95%" stopColor={color} stopOpacity={0} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#2a2d50" vertical={false} opacity={0.5} />

                        <XAxis
                            dataKey="time"
                            type="number"
                            domain={['dataMin', 'dataMax']}
                            hide={true}
                        />

                        <YAxis
                            domain={[minPrice, maxPrice]}
                            hide={true}
                        />

                        <Tooltip
                            contentStyle={{
                                backgroundColor: 'rgba(15, 16, 38, 0.95)',
                                borderColor: '#2a2d50',
                                color: '#fff',
                                fontSize: '12px',
                                boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
                                padding: '8px'
                            }}
                            labelFormatter={(label) => new Date(label * 1000).toLocaleTimeString()}
                            formatter={(value) => [`$${value.toFixed(2)}`, 'Price']}
                        />

                        <Area
                            type="monotone"
                            dataKey="price"
                            stroke={color}
                            fillOpacity={1}
                            fill={`url(#gradient-${symbol})`}
                            strokeWidth={2}
                            isAnimationActive={false}
                        />
                    </AreaChart>
                </ResponsiveContainer>

                {data.length > 0 && (
                    <div style={{
                        position: 'absolute',
                        top: '5px',
                        right: '5px',
                        fontSize: '0.9rem',
                        fontWeight: 'bold',
                        color: '#fff'
                    }}>
                        ${data[data.length - 1].price.toFixed(2)}
                    </div>
                )}
            </div>
        </div>
    );
};

export default StockChart;
