// services/web/js/core/state.js

export const state = {
    API_BASE: 'http://127.0.0.1:8000',
    currentMode: 'manual',
    currentUrl: '',
    configuredFields: [],
    smartSuggestions: [],
    selectedSuggestions: new Set(),
    fieldsConfirmed: false,
    currentRunId: null
};