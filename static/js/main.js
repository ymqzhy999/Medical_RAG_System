// static/js/main.js
import { state } from './modules/state.js';
import { ui } from './modules/ui.js';
import { sendMessage } from './controllers/chat.js';
import { loadSessions, handleNewChat, setupSessionListeners } from './controllers/session.js';
import { setupProfileListeners } from './controllers/profile.js';

function getTextFromLastUserMessage() {
    const container = document.getElementById('messages-container');
    if (!container) return '';
    const nodes = Array.from(container.querySelectorAll('.message.user .bubble'));
    const last = nodes[nodes.length - 1];
    return (last ? last.innerText : '').trim();
}

function getTextFromPairedUserMessage(regenBtn) {
    const assistantMsg = regenBtn ? regenBtn.closest('.message.assistant') : null;
    if (!assistantMsg) return '';

    let prev = assistantMsg.previousElementSibling;
    while (prev) {
        if (prev.classList && prev.classList.contains('user')) {
            const bubble = prev.querySelector('.bubble');
            return (bubble ? bubble.innerText : '').trim();
        }
        prev = prev.previousElementSibling;
    }
    return '';
}

window.triggerRegenerate = async (regenBtn) => {
    if (window.__regenBusy) return;

    const input = document.getElementById('user-input');
    if (!input) return;

    const question = getTextFromPairedUserMessage(regenBtn) || getTextFromLastUserMessage();
    if (!question) {
        ui.showToast('找不到要重新生成的问题');
        return;
    }

    window.__regenBusy = true;
    const icon = regenBtn ? regenBtn.querySelector('i') : null;
    const oldIcon = icon ? icon.className : '';
    if (regenBtn) regenBtn.disabled = true;
    if (icon) icon.className = 'fa-solid fa-spinner fa-spin';

    try {
        input.value = question;
        input.focus();
        await sendMessage();
    } finally {
        window.__regenBusy = false;
        if (regenBtn) regenBtn.disabled = false;
        if (icon) icon.className = oldIcon || 'fa-solid fa-rotate-right';
    }
};

window.safeTriggerRegenerate = async (regenBtn) => {
    if (typeof window.triggerRegenerate === 'function') {
        try {
            await window.triggerRegenerate(regenBtn);
        } catch (error) {
            console.error('Error in triggerRegenerate:', error);
            ui.showToast('重新生成时出现错误，请稍后重试');
        }
    } else {
        console.warn('triggerRegenerate function is not defined');
        ui.showToast('功能暂时不可用，请刷新页面重试');
    }
};

document.addEventListener('DOMContentLoaded', () => {
    console.log("App Starting...");

    if (!state.userId) {
        if (window.location.pathname !== '/' && window.location.pathname !== '/index.html') {
            window.location.href = '/';
        }
    }

    // 初始化 UI
    const nameEl = document.getElementById('top-username');
    if (nameEl) nameEl.innerText = state.username || '用户';
    const topAvatarText = document.getElementById('top-avatar');
    if (topAvatarText) topAvatarText.innerText = (state.username || 'U').charAt(0).toUpperCase();

    ui.initTheme();

    // 绑定事件
    const sendBtn = document.getElementById('send-btn');
    if (sendBtn) sendBtn.addEventListener('click', sendMessage);

    const inputEl = document.getElementById('user-input');
    if (inputEl) {
        inputEl.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }

    const newChatBtn = document.querySelector('.new-chat-btn');
    if (newChatBtn) newChatBtn.addEventListener('click', () => handleNewChat(true));

    const themeBtn = document.getElementById('theme-btn');
    if (themeBtn) themeBtn.addEventListener('click', () => ui.toggleTheme());

    // 左上角菜单按钮 (这里绑定一次就够了！)
    const toggleBtn = document.getElementById('toggle-menu-btn') || document.querySelector('.toggle-sidebar-btn');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            ui.toggleSidebar();
        });
    }

    // 全局函数暴露
    window.toggleSidebar = ui.toggleSidebar;
    // ui.js 里没有这个方法，要手动指向 hide
    window.closeCustomAlert = () => ui.hide('custom-alert-modal');

    // 初始化模块
    setupSessionListeners();
    setupProfileListeners();
    loadSessions();

    console.log("App Initialized Successfully");
});
