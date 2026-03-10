import { api } from '../modules/api.js';
import { state } from '../modules/state.js';
import { ui } from '../modules/ui.js';
import { renderMessages } from './chat.js';

// 加载会话列表
export async function loadSessions() {
    try {
        const sessions = await api.getSessions(state.userId);
        const listContainer = document.getElementById('history-list');
        listContainer.innerHTML = '';

        if (sessions.length === 0) {
            listContainer.innerHTML = '<div style="padding:20px;text-align:center;font-size:12px;opacity:0.6">暂无记录</div>';
            return;
        }

        const label = document.createElement('div');
        label.className = 'date-label';
        label.innerText = '近期对话';
        listContainer.appendChild(label);

        sessions.forEach(session => {
            const item = document.createElement('div');
            item.className = `history-item ${session.id === state.currentSessionId ? 'active' : ''}`;
            const title = session.title.length > 14 ? session.title.substring(0, 14) + '...' : session.title;

            item.innerHTML = `
                <span class="chat-title-text" title="${session.title}">
                    <i class="fa-regular fa-message" style="margin-right:8px;font-size:12px"></i> 
                    ${title}
                </span>
                <button class="more-options-btn" onclick="toggleContextMenu(event, 'menu-${session.id}')">
                    <i class="fa-solid fa-ellipsis-vertical"></i>
                </button>
                <div id="menu-${session.id}" class="context-menu">
                    <div class="menu-item" onclick="openRenameModal(event, ${session.id}, '${session.title}')">
                        <i class="fa-solid fa-pen"></i> 重命名
                    </div>
                    <div class="menu-item delete" onclick="deleteSession(event, ${session.id})">
                        <i class="fa-regular fa-trash-can"></i> 删除
                    </div>
                </div>
            `;
            item.onclick = (e) => {
                if(e.target.closest('.more-options-btn') || e.target.closest('.context-menu')) return;
                switchSession(session.id, session.title);
            };
            listContainer.appendChild(item);
        });
    } catch (e) { console.error(e); }
}

// 切换当前会话
export async function switchSession(sessionId, title) {
    state.setCurrentSession(sessionId);
    document.querySelector('.current-topic').innerText = title;

    const container = document.getElementById('messages-container');
    container.innerHTML = '<div style="text-align:center;padding:20px;color:#999"><i class="fa-solid fa-spinner fa-spin"></i> 加载中...</div>';

    loadSessions();

    try {
        const msgs = await api.getSessionMessages(sessionId);
        container.innerHTML = '';
        renderMessages(msgs);
    } catch (e) {
        container.innerHTML = '加载失败';
    }
}

// 创建新对话
export async function handleNewChat(refresh=true) {
    try {
        const session = await api.createSession(state.userId);
        state.setCurrentSession(session.id);
        document.querySelector('.current-topic').innerText = "新问诊对话";
        if (refresh) {
            document.getElementById('messages-container').innerHTML = '';
            loadSessions();
        }
        return session;
    } catch (e) { console.error(e); }
}

// 全局函数：菜单操作
window.toggleContextMenu = (e, id) => ui.toggleContextMenu(e, id);

// 删除会话流程
window.deleteSession = (e, id) => {
    e.stopPropagation();
    state.setSessionToDelete(id);
    ui.show('delete-modal');
};

window.closeDeleteModal = () => {
    state.setSessionToDelete(null);
    ui.hide('delete-modal');
};

window.confirmDeleteAction = async () => {
    if (!state.sessionToDeleteId) return;
    const btn = document.getElementById('confirm-delete-btn');
    const originalText = btn.innerText;
    btn.innerText = "删除中...";
    btn.disabled = true;

    try {
        const res = await api.deleteSession(state.sessionToDeleteId);
        ui.hide('delete-modal');

        if (res.status === "ok" || res.ok) {
            if (state.currentSessionId === state.sessionToDeleteId) {
                state.setCurrentSession(null);
                document.getElementById('messages-container').innerHTML = '';
                document.querySelector('.current-topic').innerText = "新问诊对话";
            }
            loadSessions();
        } else {
            alert("删除失败");
        }
    } catch (e) {
        console.error(e);
        alert("删除出错");
    } finally {
        btn.innerText = originalText;
        btn.disabled = false;
        state.setSessionToDelete(null);
    }
};

// 重命名流程
let renameId = null;
window.openRenameModal = (e, id, title) => {
    e.stopPropagation();
    ui.closeAllMenus();
    renameId = id;
    const input = document.getElementById('rename-input');
    input.value = title;
    ui.show('rename-modal');
    input.focus();
};

window.closeRenameModal = () => {
    renameId = null;
    ui.hide('rename-modal');
};

// 初始化监听器
export function setupSessionListeners() {
    const renameBtn = document.getElementById('confirm-rename-btn');
    if (renameBtn) {
        renameBtn.onclick = async () => {
            const newTitle = document.getElementById('rename-input').value.trim();
            if (!newTitle || !renameId) return;
            try {
                await api.renameSession(renameId, newTitle);
                ui.hide('rename-modal');
                loadSessions();
                if (state.currentSessionId === renameId) {
                    document.querySelector('.current-topic').innerText = newTitle;
                }
            } catch(e) { console.error(e); }
        };
    }

    const deleteBtn = document.getElementById('confirm-delete-btn');
    if (deleteBtn) {
        deleteBtn.onclick = window.confirmDeleteAction;
    }

    document.addEventListener('click', (e) => {
        if (!e.target.closest('.more-options-btn') && !e.target.closest('.context-menu')) {
            ui.closeAllMenus();
        }
    });
}