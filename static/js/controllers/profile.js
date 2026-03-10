import { api } from '../modules/api.js';
import { state } from '../modules/state.js';
import { ui } from '../modules/ui.js';

// 打开个人资料模态框
window.openProfileModal = () => {
    document.getElementById('profile-username-display').innerText = state.username || '用户';
    document.getElementById('profile-email-display').innerText = `${state.username}@example.com`;

    const textAvatar = document.getElementById('profile-avatar-text');
    if (textAvatar) textAvatar.innerText = (state.username || 'U').charAt(0).toUpperCase();

    const savedAvatar = localStorage.getItem('avatar_url');
    if (savedAvatar) ui.updateAvatarUI(savedAvatar);

    ui.show('profile-modal');
};

window.closeProfileModal = () => ui.hide('profile-modal');

window.triggerAvatarUpload = () => document.getElementById('avatar-input').click();

// 处理头像上传
window.handleAvatarSelected = async (input) => {
    if (input.files && input.files[0]) {
        const formData = new FormData();
        formData.append('file', input.files[0]);

        const iconContainer = document.querySelector('.camera-badge');
        let oldIconHTML = '';
        if (iconContainer) {
            oldIconHTML = iconContainer.innerHTML;
            iconContainer.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
        }

        try {
            const data = await api.uploadAvatar(state.userId, formData);
            if (iconContainer) iconContainer.innerHTML = oldIconHTML || '<i class="fa-solid fa-camera"></i>';

            const newUrl = data.avatar_url;
            if (newUrl) {
                localStorage.setItem('avatar_url', newUrl);
                ui.updateAvatarUI(newUrl);
            }
        } catch (e) {
            alert('上传失败: ' + e.message);
            if (iconContainer) iconContainer.innerHTML = oldIconHTML || '<i class="fa-solid fa-camera"></i>';
        } finally {
            input.value = '';
        }
    }
};

window.openAccountModal = () => ui.show('account-modal');

// 修改密码
window.submitPasswordChange = async () => {
    const newPwd = document.getElementById('new-password').value;
    if(!newPwd) return ui.showAlert("提示", "密码不能为空");

    const btn = document.querySelector('#account-modal .modal-btn.confirm');
    const originalText = btn.innerText;
    btn.innerText = "提交中...";
    btn.disabled = true;

    try {
        await api.updatePassword(state.userId, newPwd);
        ui.hide('account-modal');
        ui.showAlert("成功", "密码修改成功，请重新登录", () => {
            window.handleLogout();
        });
    } catch (e) {
        ui.showAlert("失败", e.message);
    } finally {
        btn.innerText = originalText;
        btn.disabled = false;
    }
};

// 退出登录
window.handleLogout = () => {
    localStorage.removeItem('user_id');
    localStorage.removeItem('username');
    window.location.href = '/';
};

window.addAccount = window.handleLogout;

// 初始化
export function setupProfileListeners() {
    const savedAvatar = localStorage.getItem('avatar_url');
    if (savedAvatar) ui.updateAvatarUI(savedAvatar);
}