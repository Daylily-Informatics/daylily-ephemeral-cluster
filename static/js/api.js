/**
 * Daylily Customer Portal - API Client
 */

const DaylilyAPI = {
    baseUrl: window.DaylilyConfig?.apiBase || '',

    // Generic request method
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        console.log(`API Request: ${options.method || 'GET'} ${url}`);

        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
            ...options,
        };

        // Add CSRF token if available
        if (window.DaylilyConfig?.csrfToken) {
            config.headers['X-CSRF-Token'] = window.DaylilyConfig.csrfToken;
        }

        try {
            const response = await fetch(url, config);

            if (!response.ok) {
                const error = await response.json().catch(() => ({ detail: response.statusText }));
                console.error(`API Error Response [${endpoint}]:`, error);
                throw new Error(error.detail || `HTTP ${response.status}`);
            }

            const data = await response.json();
            console.log(`API Response [${endpoint}]:`, data);
            return data;
        } catch (error) {
            console.error(`API Error [${endpoint}]:`, error);
            throw error;
        }
    },
    
    // GET request
    async get(endpoint, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = queryString ? `${endpoint}?${queryString}` : endpoint;
        return this.request(url, { method: 'GET' });
    },
    
    // POST request
    async post(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data),
        });
    },
    
    // PUT request
    async put(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    },
    
    // DELETE request
    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    },
    
    // === Customer Endpoints ===
    customers: {
        async list(params = {}) {
            return DaylilyAPI.get('/api/customers', params);
        },
        async get(customerId) {
            return DaylilyAPI.get(`/api/customers/${customerId}`);
        },
        async create(data) {
            return DaylilyAPI.post('/api/customers', data);
        },
        async update(customerId, data) {
            return DaylilyAPI.put(`/api/customers/${customerId}`, data);
        },
    },
    
    // === Workset Endpoints ===
    worksets: {
        async list(customerId, params = {}) {
            return DaylilyAPI.get(`/api/customers/${customerId}/worksets`, params);
        },
        async get(customerId, worksetId) {
            return DaylilyAPI.get(`/api/customers/${customerId}/worksets/${worksetId}`);
        },
        async create(customerId, data) {
            return DaylilyAPI.post(`/api/customers/${customerId}/worksets`, data);
        },
        async cancel(customerId, worksetId) {
            return DaylilyAPI.post(`/api/customers/${customerId}/worksets/${worksetId}/cancel`);
        },
        async retry(customerId, worksetId) {
            return DaylilyAPI.post(`/api/customers/${customerId}/worksets/${worksetId}/retry`);
        },
        async getLogs(customerId, worksetId) {
            return DaylilyAPI.get(`/api/customers/${customerId}/worksets/${worksetId}/logs`);
        },
        async archive(customerId, worksetId, reason) {
            return DaylilyAPI.post(`/api/customers/${customerId}/worksets/${worksetId}/archive`, { reason });
        },
        async delete(customerId, worksetId, hardDelete, reason) {
            return DaylilyAPI.post(`/api/customers/${customerId}/worksets/${worksetId}/delete`, { hard_delete: hardDelete, reason });
        },
        async restore(customerId, worksetId) {
            return DaylilyAPI.post(`/api/customers/${customerId}/worksets/${worksetId}/restore`);
        },
        async listArchived(customerId) {
            return DaylilyAPI.get(`/api/customers/${customerId}/worksets/archived`);
        },
    },
    
    // === File Endpoints ===
    files: {
        async list(customerId, prefix = '') {
            return DaylilyAPI.get(`/api/customers/${customerId}/files`, { prefix });
        },
        async upload(customerId, file, prefix = '') {
            // Use FormData for file upload
            const formData = new FormData();
            formData.append('file', file);
            formData.append('prefix', prefix);

            const url = `${DaylilyAPI.baseUrl}/api/customers/${customerId}/files/upload`;
            console.log(`Uploading file to: ${url}`);

            const response = await fetch(url, {
                method: 'POST',
                body: formData,
                // Don't set Content-Type header - browser will set it with boundary for FormData
            });

            if (!response.ok) {
                const error = await response.json().catch(() => ({ detail: response.statusText }));
                throw new Error(error.detail || `HTTP ${response.status}`);
            }

            return await response.json();
        },
        async createFolder(customerId, folderPath) {
            return DaylilyAPI.post(`/api/customers/${customerId}/files/create-folder`, {
                folder_path: folderPath,
            });
        },
        async delete(customerId, key) {
            return DaylilyAPI.delete(`/api/customers/${customerId}/files/${encodeURIComponent(key)}`);
        },
        async getDownloadUrl(customerId, key) {
            return DaylilyAPI.get(`/api/customers/${customerId}/files/${encodeURIComponent(key)}/download-url`);
        },
        async preview(customerId, key, lines = 20) {
            return DaylilyAPI.get(`/api/customers/${customerId}/files/${encodeURIComponent(key)}/preview`, { lines });
        },
    },
    
    // === Usage Endpoints ===
    usage: {
        async get(customerId, params = {}) {
            return DaylilyAPI.get(`/api/customers/${customerId}/usage`, params);
        },
        async getDetails(customerId, params = {}) {
            return DaylilyAPI.get(`/api/customers/${customerId}/usage/details`, params);
        },
    },
    
    // === Dashboard Stats ===
    dashboard: {
        async getStats(customerId) {
            return DaylilyAPI.get(`/api/customers/${customerId}/dashboard/stats`);
        },
        async getActivity(customerId, days = 30) {
            return DaylilyAPI.get(`/api/customers/${customerId}/dashboard/activity`, { days });
        },
    },
};

// Refresh dashboard stats
async function refreshDashboardStats() {
    const customerId = window.DaylilyConfig?.customerId;
    if (!customerId) return;
    
    try {
        const stats = await DaylilyAPI.dashboard.getStats(customerId);
        
        // Update stat cards
        const activeEl = document.getElementById('stat-active-worksets');
        if (activeEl) activeEl.textContent = stats.active_worksets || 0;
        
        const completedEl = document.getElementById('stat-completed');
        if (completedEl) completedEl.textContent = stats.completed_worksets || 0;
        
        const storageEl = document.getElementById('stat-storage');
        if (storageEl) storageEl.textContent = (stats.storage_used_gb || 0).toFixed(1);
        
    } catch (error) {
        console.error('Failed to refresh dashboard stats:', error);
    }
}

