import { DataProvider, fetchUtils } from 'react-admin';

const API_URL = import.meta.env.VITE_API_URL || '/api';

const httpClient = fetchUtils.fetchJson;

/**
 * Custom Data Provider for Shri Travels Admin Panel
 * Connects to FastAPI backend REST API
 */
export const dataProvider: DataProvider = {
  // Get list with pagination, sorting, and filtering
  getList: async (resource, params) => {
    const { page, perPage } = params.pagination || { page: 1, perPage: 10 };
    const { field, order } = params.sort || { field: 'id', order: 'DESC' };
    const { filter } = params;

    const query = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
      sort_by: field,
      sort_order: order.toLowerCase(),
    });

    // Add filters
    if (filter) {
      Object.keys(filter).forEach((key) => {
        if (filter[key] !== undefined && filter[key] !== '') {
          query.append(key, String(filter[key]));
        }
      });
    }

    const url = `${API_URL}/${resource}?${query.toString()}`;
    const { json } = await httpClient(url);

    return {
      data: json.data,
      total: json.total,
    };
  },

  // Get one record by ID
  getOne: async (resource, params) => {
    const url = `${API_URL}/${resource}/${params.id}`;
    const { json } = await httpClient(url);
    return { data: json };
  },

  // Get multiple records by IDs
  getMany: async (resource, params) => {
    const results = await Promise.all(
      params.ids.map((id) =>
        httpClient(`${API_URL}/${resource}/${id}`).then(({ json }) => json)
      )
    );
    return { data: results };
  },

  // Get related records (for references)
  getManyReference: async (resource, params) => {
    const { page, perPage } = params.pagination || { page: 1, perPage: 10 };
    const { field, order } = params.sort || { field: 'id', order: 'DESC' };

    const query = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
      sort_by: field,
      sort_order: order.toLowerCase(),
      [params.target]: String(params.id),
    });

    const url = `${API_URL}/${resource}?${query.toString()}`;
    const { json } = await httpClient(url);

    return {
      data: json.data,
      total: json.total,
    };
  },

  // Create a new record
  create: async (resource, params) => {
    const url = `${API_URL}/${resource}`;
    const { json } = await httpClient(url, {
      method: 'POST',
      body: JSON.stringify(params.data),
    });
    return { data: json };
  },

  // Update a record
  update: async (resource, params) => {
    const url = `${API_URL}/${resource}/${params.id}`;
    const { json } = await httpClient(url, {
      method: 'PATCH',
      body: JSON.stringify(params.data),
    });
    return { data: json };
  },

  // Update multiple records
  updateMany: async (resource, params) => {
    const results = await Promise.all(
      params.ids.map((id) =>
        httpClient(`${API_URL}/${resource}/${id}`, {
          method: 'PATCH',
          body: JSON.stringify(params.data),
        })
      )
    );
    return { data: params.ids };
  },

  // Delete a record
  delete: async (resource, params) => {
    const url = `${API_URL}/${resource}/${params.id}`;
    const { json } = await httpClient(url, { method: 'DELETE' });
    return { data: params.previousData };
  },

  // Delete multiple records
  deleteMany: async (resource, params) => {
    await Promise.all(
      params.ids.map((id) =>
        httpClient(`${API_URL}/${resource}/${id}`, { method: 'DELETE' })
      )
    );
    return { data: params.ids };
  },
};

// Custom API calls for chat functionality
export const chatApi = {
  // Get dashboard stats
  getDashboardStats: async () => {
    const { json } = await httpClient(`${API_URL}/dashboard/stats`);
    return json;
  },

  // Get conversations list
  getConversations: async (page = 1, perPage = 20, unreadOnly = false) => {
    const query = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
      unread_only: String(unreadOnly),
    });
    const { json } = await httpClient(`${API_URL}/conversations?${query}`);
    return json;
  },

  // Get messages for a user
  getMessages: async (userId: number, page = 1, perPage = 50) => {
    const query = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    const { json } = await httpClient(
      `${API_URL}/users/${userId}/messages?${query}`
    );
    return json;
  },

  // Send admin message
  sendMessage: async (userId: number, content: string, sendWhatsapp = true) => {
    const { json } = await httpClient(`${API_URL}/messages/send`, {
      method: 'POST',
      body: JSON.stringify({
        user_id: userId,
        content,
        send_whatsapp: sendWhatsapp,
      }),
    });
    return json;
  },

  // Toggle bot status
  toggleBotStatus: async (userId: number) => {
    const { json } = await httpClient(`${API_URL}/users/${userId}/toggle-bot`, {
      method: 'POST',
    });
    return json;
  },

  // Mark messages as read
  markAsRead: async (userId: number) => {
    const { json } = await httpClient(
      `${API_URL}/users/${userId}/messages/mark-read`,
      { method: 'POST' }
    );
    return json;
  },

  // Sync customers from knowledge graph
  syncCustomers: async () => {
    const { json } = await httpClient(`${API_URL}/sync/customers`, {
      method: 'POST',
    });
    return json;
  },
};
