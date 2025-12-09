import axios from 'axios';
import { io } from 'socket.io-client';

const API_URL = 'http://localhost:5000';

export const api = axios.create({
    baseURL: API_URL
});

export const socket = io(API_URL, {
    transports: ['websocket'],
    reconnection: true
});
