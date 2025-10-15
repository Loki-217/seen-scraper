// services/web/js/core/api.js

import { state } from './state.js';

export const api = {
    async renderPage(url) {
        const response = await fetch(`${state.API_BASE}/api/proxy/render`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, timeout_ms: 30000 })
        });
        return response;
    },
    
    async analyzePageSmart(url, config) {
        const response = await fetch(`${state.API_BASE}/api/smart/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, ...config })
        });
        return response.json();
    },
    
    async suggestFieldName(element, context) {
        const response = await fetch(`${state.API_BASE}/api/ai/suggest-field-name`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ element, context })
        });
        return response.json();
    },
    
    async createJob(jobData) {
        const response = await fetch(`${state.API_BASE}/jobs`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(jobData)
        });
        return response.json();
    },
    
    async runJob(jobId, payload) {
        const response = await fetch(`${state.API_BASE}/runs/jobs/${jobId}/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        return response.json();
    },
    
    async getRunStatus(runId) {
        const response = await fetch(`${state.API_BASE}/runs/${runId}`);
        return response.json();
    },
    
    async getResults(runId) {
        const response = await fetch(`${state.API_BASE}/runs/${runId}/results`);
        return response.json();
    }
};