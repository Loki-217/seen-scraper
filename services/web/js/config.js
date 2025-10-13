// 全局配置
export const CONFIG = {
    API_BASE: 'http://127.0.0.1:8000',
    
    BRAND: {
        name: 'SeenFetch',
        version: '1.0.0',
        tagline: 'See it, Fetch it'
    },
    
    DEFAULTS: {
        MAX_ITEMS: 100,
        TIMEOUT_MS: 30000
    },
    
    ENDPOINTS: {
        RENDER: '/api/proxy/render',
        SMART_ANALYZE: '/api/smart/analyze',
        AI_SUGGEST: '/api/ai/suggest-field-name',
        JOBS: '/jobs',
        RUNS: '/runs'
    }
};