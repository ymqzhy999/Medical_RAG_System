const API_PREFIX = "/api/chat";

async function request(url, options = {}) {
    const finalUrl = `${API_PREFIX}${url}`;
    try {
        const res = await fetch(finalUrl, options);
        if (!res.ok && !options.stream) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || '请求失败');
        }
        return res;
    } catch (e) {
        console.error("API请求错误:", e);
        throw e;
    }
}

export const api = {
    // 会话相关
    getSessions: (userId) => request(`/sessions?user_id=${userId}`).then(r => r.json()),
    createSession: (userId) => request('/sessions', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({user_id: userId})
    }).then(r => r.json()),
    deleteSession: (id) => request(`/sessions/${id}`, { method: 'DELETE' }).then(r => r.json()),
    renameSession: (id, title) => request(`/sessions/${id}/rename`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title })
    }).then(r => r.json()),
    getSessionMessages: (sessionId) => request(`/sessions/${sessionId}/messages`).then(r => r.json()),

    // 消息发送
    sendMessage: (userId, sessionId, content) => request('/send', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({user_id: userId, session_id: sessionId, content}),
        stream: true
    }),

    // 用户与反馈
    uploadAvatar: (userId, formData) => request(`/users/${userId}/avatar`, {
        method: 'POST',
        body: formData
    }).then(r => r.json()),
    updatePassword: (userId, password) => request(`/users/${userId}/password`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({password})
    }).then(r => r.json()),
    sendFeedback: (msgId, action) => request(`/messages/${msgId}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action })
    }).then(r => r.json())
};