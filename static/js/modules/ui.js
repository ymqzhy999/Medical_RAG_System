import { api } from './api.js';

export const ui = {
    show(id) {
        const el = document.getElementById(id);
        if (el) el.style.display = 'flex';
    },
    hide(id) {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    },

    closeCustomAlert() {
        this.hide('custom-alert-modal');
    },

    showAlert(title, msg, callback) {
        const titleEl = document.getElementById('alert-title');
        const msgEl = document.getElementById('alert-message');
        if (titleEl) titleEl.innerText = title;
        if (msgEl) msgEl.innerText = msg;

        this.show('custom-alert-modal');

        window.tempAlertCallback = () => {
            this.hide('custom-alert-modal');
            if (callback) callback();
        };
        const btn = document.querySelector('#custom-alert-modal .modal-btn.confirm');
        if (btn) btn.onclick = window.tempAlertCallback;
    },

    scrollToBottom() {
        const container = document.getElementById('messages-container');
        if (container) container.scrollTop = container.scrollHeight;
    },

    initTheme() {
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'dark') {
            document.body.classList.add('dark-mode');
            this.updateThemeIcon(true);
        }
    },
    toggleTheme() {
        document.body.classList.toggle('dark-mode');
        const isDark = document.body.classList.contains('dark-mode');
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
        this.updateThemeIcon(isDark);
    },
    updateThemeIcon(isDark) {
        const btn = document.getElementById('theme-btn');
        if (btn) btn.innerHTML = isDark ? '<i class="fa-solid fa-sun"></i>' : '<i class="fa-solid fa-moon"></i>';
    },


    toggleSidebar() {
        const sidebar = document.getElementById('sidebar');
        if (sidebar) {
            sidebar.classList.toggle('collapsed');
            sidebar.classList.toggle('show');
            sidebar.classList.toggle('active');
        }
        const overlay = document.querySelector('.sidebar-overlay');
        if (overlay) overlay.classList.toggle('active');
    },

    openSourceSidebar(src) {
        const sidebar = document.getElementById('source-sidebar');
        const title = document.getElementById('sidebar-title');
        const content = document.getElementById('sidebar-content');

        if (sidebar && title && content) {
            title.textContent = src.title || "未知来源";

            content.textContent = src.full_content || src.snippet || "暂无详细内容";

            sidebar.classList.add('active');


            sidebar.style.visibility = '';
            sidebar.style.right = '';
        }
    },

    closeAllMenus() {
        document.querySelectorAll('.context-menu').forEach(el => el.classList.remove('show'));
        document.querySelectorAll('.more-options-btn').forEach(el => el.classList.remove('active'));
    },
    toggleContextMenu(e, menuId) {
        e.stopPropagation();
        const menu = document.getElementById(menuId);
        const btn = e.currentTarget;

        if (menu.classList.contains('show')) {
            menu.classList.remove('show');
            btn.classList.remove('active');
        } else {
            this.closeAllMenus();
            menu.classList.add('show');
            btn.classList.add('active');
        }
    },


    updateAvatarUI(url) {
        if (!url) return;
        const topAvatar = document.getElementById('top-avatar');
        if (topAvatar) topAvatar.innerHTML = `<img src="${url}" style="width:100%;height:100%;border-radius:50%;object-fit:cover;">`;

        const profileAvatar = document.querySelector('.profile-avatar-large');
        if (profileAvatar) {
            const badge = profileAvatar.querySelector('.camera-badge');
            const badgeHTML = badge ? badge.outerHTML : '';
            profileAvatar.innerHTML = `<img src="${url}" style="width:100%;height:100%;border-radius:50%;object-fit:cover;">` + badgeHTML;
        }
    },

    showToast(message) {
        const existing = document.querySelector('.global-toast');
        if (existing) existing.remove();

        // 2. 创建新元素
        const toast = document.createElement('div');
        toast.className = 'global-toast';
        toast.innerHTML = `<i class="fa-solid fa-circle-check"></i> <span>${message}</span>`;

        // 3. 添加到 body (fixed定位)
        document.body.appendChild(toast);

        // 4. 3秒后自动移除 (配合 CSS 动画时间)
        setTimeout(() => {
            if (toast && toast.parentElement) {
                toast.remove();
            }
        }, 3000);
    },

    createMessageDiv(role, htmlContent, feedback = 0, messageId = null) {
        const div = document.createElement('div');
        div.className = `message ${role}`;

        if (messageId) div.dataset.id = messageId;

        const icon = role === 'user' ? '' : '<div class="avatar"><i class="fa-solid fa-wand-magic-sparkles"></i></div>';

        let actionsHTML = '';
        if (role === 'assistant') {

            const likeClass = feedback === 1 ? 'active-like' : '';
            const likeIcon = feedback === 1 ? 'fa-solid fa-thumbs-up' : 'fa-regular fa-thumbs-up';

            const dislikeClass = feedback === -1 ? 'active-dislike' : '';
            const dislikeIcon = feedback === -1 ? 'fa-solid fa-thumbs-down' : 'fa-regular fa-thumbs-down';

            actionsHTML = `
                <div class="message-actions">
                    <button class="action-btn" onclick="ui.handleCopy(this)" title="复制">
                        <i class="fa-regular fa-copy"></i>
                    </button>
                    <button class="action-btn ${likeClass}" onclick="ui.handleLike(this, 'like')" title="点赞">
                        <i class="${likeIcon}"></i>
                    </button>
                    <button class="action-btn ${dislikeClass}" onclick="ui.handleLike(this, 'dislike')" title="点踩">
                        <i class="${dislikeIcon}"></i>
                    </button>
                    <button class="action-btn regenerate-btn" onclick="window.safeTriggerRegenerate ? window.safeTriggerRegenerate(this) : window.triggerRegenerate && window.triggerRegenerate(this)" title="重新生成">
                        <i class="fa-solid fa-rotate-right"></i>
                    </button>
                </div>
            `;
        }

        // 组装 HTML
        div.innerHTML = `
            ${icon}
            <div class="bubble-container">
                <div class="bubble">${htmlContent}</div>
                <div class="sources-area"></div> 
                ${actionsHTML} 
            </div>
        `;
        return div;
    },

    handleCopy(btn) {
        // 1. 找到气泡里的纯文本
        const bubble = btn.closest('.bubble-container').querySelector('.bubble');
        const text = bubble.innerText;

        navigator.clipboard.writeText(text).then(() => {
            // A. 按钮图标变为对勾
            const icon = btn.querySelector('i');
            icon.className = "fa-solid fa-check";
            setTimeout(() => {
                icon.className = "fa-regular fa-copy";
            }, 1500);

            // B. 屏幕左下角弹出提示
            this.showToast("已复制到剪贴板");

        }).catch(err => {
            console.error('复制失败:', err);
            this.showToast("复制失败，请手动复制");
        });
    },

    handleLike(btn, type) {
        const messageDiv = btn.closest('.message');
        const bubble = messageDiv.querySelector('.bubble');

        const msgId = messageDiv.dataset.id || (bubble ? bubble.dataset.messageId : null);

        // 2. 获取相关按钮 DOM
        const parent = btn.parentElement;
        const likeBtn = parent.querySelector('[title="点赞"]');
        const dislikeBtn = parent.querySelector('[title="点踩"]');

        let action = 'cancel'; // 默认为取消操作

        // 3. 视觉逻辑处理 (切换类名和图标)
        if (type === 'like') {
            // --- 点击了【点赞】 ---
            if (likeBtn.classList.contains('active-like')) {
                // 状态：已赞 -> 取消赞
                likeBtn.classList.remove('active-like');
                likeBtn.querySelector('i').className = "fa-regular fa-thumbs-up"; // 变空心
                action = 'cancel';
            } else {
                likeBtn.classList.add('active-like');
                likeBtn.querySelector('i').className = "fa-solid fa-thumbs-up"; // 变实心

                if (dislikeBtn.classList.contains('active-dislike')) {
                    dislikeBtn.classList.remove('active-dislike');
                    dislikeBtn.querySelector('i').className = "fa-regular fa-thumbs-down";
                }
                action = 'like';
            }
        } else {
            if (dislikeBtn.classList.contains('active-dislike')) {
                dislikeBtn.classList.remove('active-dislike');
                dislikeBtn.querySelector('i').className = "fa-regular fa-thumbs-down"; // 变空心
                action = 'cancel';
            } else {
                dislikeBtn.classList.add('active-dislike');
                dislikeBtn.querySelector('i').className = "fa-solid fa-thumbs-down"; // 变实心

                if (likeBtn.classList.contains('active-like')) {
                    likeBtn.classList.remove('active-like');
                    likeBtn.querySelector('i').className = "fa-regular fa-thumbs-up";
                }
                action = 'dislike';
            }
        }

        if (msgId) {
            api.sendFeedback(msgId, action)
                .then(res => {
                    console.log(`反馈成功: ID=${msgId}, Action=${action}`);
                })
                .catch(err => {
                    console.error("反馈失败:", err);
                });
        } else {
            console.log("ℹ️ 系统欢迎语或无ID消息，仅做前端展示，不保存到数据库。");
        }
    },

    renderSources(container, sources) {
        if (!sources || sources.length === 0) return;

        if (container.innerHTML !== "") return;

        const toggleBtn = document.createElement('button');
        toggleBtn.className = 'sources-toggle';
        toggleBtn.innerHTML = `<i class="fa-solid fa-book-medical"></i> 参考来源 (${sources.length})`;

        const listDiv = document.createElement('div');
        listDiv.className = 'sources-list';
        listDiv.style.display = 'grid';

        sources.forEach(src => {
            const card = document.createElement('div');
            card.className = 'source-card-mini';
            card.innerHTML = `
                <div class="source-title-mini">📄 ${src.title}</div>
            `;

            card.onclick = () => {
                this.openSourceSidebar(src);
            };

            listDiv.appendChild(card);
        });

        toggleBtn.onclick = () => {
            const isHidden = listDiv.style.display === 'none';
            listDiv.style.display = isHidden ? 'grid' : 'none';
        };

        container.appendChild(toggleBtn);
        container.appendChild(listDiv);
    }
};


window.ui = ui;
