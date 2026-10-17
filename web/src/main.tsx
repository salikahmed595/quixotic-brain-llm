import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import './index.css';

/* Opened straight from disk? That page can never reach the backend, so go to the real address instead. */
if (location.protocol === 'file:') location.replace('http://localhost:8000/');
else createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);
