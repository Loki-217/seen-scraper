// services/web/js/config.js
/**
 * 🔧 SeenFetch 全局配置
 */

export const CONFIG = {
    // 品牌信息
    BRAND: {
        name: 'SeenFetch',
        version: '1.0.0',
        tagline: 'See it, Fetch it',
        description: 'Visual Web Data Extraction',
        author: 'SeenFetch Team',
        website: 'https://seenfetch.io'
    },
    
    // API 配置
    API: {
        BASE_URL: 'http://127.0.0.1:8000',
        TIMEOUT: 30000,
        ENDPOINTS: {
            HEALTH: '/health',
            RENDER: '/api/proxy/render',
            SMART_ANALYZE: '/api/smart/analyze',
            AI_SUGGEST: '/api/ai/suggest-field-name',
            JOBS: '/jobs',
            RUNS: '/runs'
        }
    },
    
    // 默认设置
    DEFAULTS: {
        MAX_ITEMS: 100,
        AUTO_PAGING: true,
        REMOVE_DUPLICATES: true,
        TIMEOUT_MS: 30000
    },
    
    // 模式
    MODES: {
        MANUAL: 'manual',
        SMART: 'smart'
    },
    
    // 字段类型
    FIELD_TYPES: {
        TEXT: 'text',
        LINK: 'link',
        IMAGE: 'image',
        PRICE: 'price',
        DATE: 'date'
    },
    
    // UI 配置
    UI: {
        TOAST_DURATION: 5000,
        ANIMATION_DURATION: 300
    }
};

export default CONFIG;