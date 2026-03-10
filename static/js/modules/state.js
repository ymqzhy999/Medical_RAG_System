export const state = {
    userId: localStorage.getItem('user_id'),
    username: localStorage.getItem('username'),
    currentSessionId: null,
    sessionToDeleteId: null,

    // 设置当前会话ID
    setCurrentSession(id) {
        this.currentSessionId = id;
    },

    // 设置待删除会话ID
    setSessionToDelete(id) {
        this.sessionToDeleteId = id;
    }
};