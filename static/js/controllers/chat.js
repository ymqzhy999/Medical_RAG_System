import { api } from '../modules/api.js';
import { state } from '../modules/state.js';
import { ui } from '../modules/ui.js';
import { handleNewChat, loadSessions } from './session.js';

// Markdown 格式化工具
function makeTextPretty(text) {
    if (!text) return '';
    let safeText = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    safeText = safeText.replace(/### (.*?)(<br>|\n|$)/g, '<h3>$1</h3>');
    safeText = safeText.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    safeText = safeText.replace(/^\s*-\s+(.*?)(\n|$)/gm, '<li>$1</li>');
    safeText = safeText.replace(/\n/g, '<br>');
    return safeText;
}

// 渲染历史消息
export function renderMessages(messageList) {
    const box = document.getElementById('messages-container');
    box.innerHTML = '';

    for (const msg of messageList) {
        const prettyHtml = makeTextPretty(msg.content);
        // 传入消息ID用于点赞反馈
        const messageDiv = ui.createMessageDiv(msg.role, prettyHtml, msg.feedback, msg.id);
        box.appendChild(messageDiv);

        if (msg.role === 'assistant' && msg.sources) {
            try {
                const sourceArea = messageDiv.querySelector('.sources-area');
                let sourceData = typeof msg.sources === 'string' ? JSON.parse(msg.sources) : msg.sources;
                ui.renderSources(sourceArea, sourceData);
            } catch(e) { }
        }
    }
    ui.scrollToBottom();
}

// 发送消息核心逻辑
export async function sendMessage() {
    const input = document.getElementById('user-input');
    const userText = input.value.trim();
    if (!userText) return;

    if (!state.currentSessionId) {
        await handleNewChat(false);
    }

    // 渲染用户消息
    const userBubble = ui.createMessageDiv('user', makeTextPretty(userText));
    document.getElementById('messages-container').appendChild(userBubble);
    ui.scrollToBottom();

    input.value = '';
    input.style.height = 'auto';

    // 创建 AI 占位气泡
    const aiBubble = ui.createMessageDiv('assistant', '<span class="cursor"></span>');
    document.getElementById('messages-container').appendChild(aiBubble);
    ui.scrollToBottom();

    const textZone = aiBubble.querySelector('.bubble');
    const sourceZone = aiBubble.querySelector('.sources-area');
    let fullText = "";

    try {
        const response = await api.sendMessage(state.userId, state.currentSessionId, userText);
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        // 处理流式响应
        while (true) {
            const {done, value} = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, {stream: true});
            const lines = buffer.split('\n\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const jsonStr = line.replace('data: ', '').trim();
                    if (!jsonStr || jsonStr === '[DONE]') continue;

                    try {
                        const data = JSON.parse(jsonStr);
                        if (data.text) {
                            fullText += data.text;
                            textZone.innerHTML = makeTextPretty(fullText) + '<span class="cursor"></span>';
                            ui.scrollToBottom();
                        } else if (data.sources) {
                            ui.renderSources(sourceZone, data.sources);
                        } else if (data.meta && data.meta.message_id) {
                            textZone.dataset.messageId = data.meta.message_id;
                            aiBubble.dataset.id = data.meta.message_id;
                        }
                    } catch (err) {}
                }
            }
        }
        textZone.innerHTML = makeTextPretty(fullText);
        loadSessions();

    } catch (err) {
        console.error(err);
        textZone.innerHTML += `<br><span style="color:red">出错了: ${err.message}</span>`;
    }
}

// 输入框自适应高度
document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('user-input');
    if (input) {
        input.addEventListener('input', function() {
            this.style.height = 'auto';
            if (this.scrollHeight > 150) {
                this.style.overflowY = "auto";
            } else {
                this.style.overflowY = "hidden";
                this.style.height = this.scrollHeight + 'px';
            }
        });
    }
});