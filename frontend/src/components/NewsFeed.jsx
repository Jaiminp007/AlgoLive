import React, { useEffect, useRef } from 'react';

const NewsFeed = ({ news }) => {
    const scrollRef = useRef(null);

    // Auto-scroll to top when new news comes? Or it's a list.
    // Usually news feeds have newest at top.

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'hidden' }}>
            {news.length === 0 ? (
                <div style={{ color: 'var(--text-secondary)', padding: '10px' }}>Waiting for headlines...</div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', overflowY: 'auto', paddingRight: '5px' }}>
                    {news.map((item, index) => (
                        <div key={index} style={{
                            padding: '10px',
                            borderRadius: '6px',
                            background: 'rgba(0,0,0,0.2)',
                            borderLeft: `3px solid ${item.sentiment > 0.2 ? '#00c853' : item.sentiment < -0.2 ? '#d50000' : '#ff9800'}`
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                                <span style={{
                                    fontSize: '0.7rem',
                                    fontWeight: 'bold',
                                    color: 'var(--text-secondary)',
                                    textTransform: 'uppercase'
                                }}>
                                    {item.symbol || 'MARKET'}
                                </span>
                                <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                                    {new Date(item.timestamp * 1000).toLocaleTimeString()}
                                </span>
                            </div>
                            <div style={{ fontSize: '0.85rem', lineHeight: '1.4' }}>
                                {item.title}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default NewsFeed;
