import { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import SelectionPage from './pages/SelectionPage';
import DashboardPage from './pages/DashboardPage';
import LeaderboardPage from './pages/LeaderboardPage';
import './index.css';

function App() {
    return (
        <Router>
            <div className="app-container">
                <Routes>
                    <Route path="/" element={<SelectionPage />} />
                    <Route path="/dashboard" element={<DashboardPage />} />
                    <Route path="/leaderboard" element={<LeaderboardPage />} />
                </Routes>
            </div>
        </Router>
    );
}

export default App;
