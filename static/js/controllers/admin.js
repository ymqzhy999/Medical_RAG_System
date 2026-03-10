const OriginalSwal = Swal;
window.Swal = OriginalSwal.mixin({
    heightAuto: false,
    allowOutsideClick: false
});

// 图表实例存储
let chartInstances = {};

window.triggerRegenerate = async (regenBtn) => {
    // 管理员界面不需要重新生成功能，显示提示信息
    if (window.Swal) {
        Swal.fire({
            title: '提示',
            text: '此功能在管理员界面中不可用',
            icon: 'info',
            background: '#1e1e1e',
            color: '#fff'
        });
    } else {
        alert('此功能在管理员界面中不可用');
    }
};

// 切换视图并保存状态
function switchView(viewName, btnElement) {
    localStorage.setItem('currentAdminView', viewName);

    document.querySelectorAll('.sidebar .menu-item').forEach(el => el.classList.remove('active'));
    if (btnElement) {
        btnElement.classList.add('active');
    } else {
        const targetBtn = Array.from(document.querySelectorAll('.sidebar .menu-item')).find(el => {
            return el.innerText.includes(
                viewName === 'chart-dashboard' ? '数据看板' :
                viewName === 'dashboard' ? '用户反馈' :
                viewName === 'users' ? '用户管理' :
                viewName === 'prompts' ? '提示词工程' : '知识库管理'
            );
        });
        if(targetBtn) targetBtn.classList.add('active');
    }

    // 隐藏所有视图
    const views = ['view-chart-dashboard', 'view-dashboard', 'view-users', 'view-prompts', 'view-knowledge'];
    views.forEach(v => {
        const el = document.getElementById(v);
        if(el) el.style.display = 'none';
    });

    // 显示对应视图
    if (viewName === 'chart-dashboard') {
        const view = document.getElementById('view-chart-dashboard');
        if(view) {
            view.style.display = 'block';
            loadChartDashboard();
            // 窗口大小改变时重新调整图表
            setTimeout(() => resizeCharts(), 100);
        }
    } else if (viewName === 'dashboard') {
        const view = document.getElementById('view-dashboard');
        if(view) {
            view.style.display = 'block';
            loadStats();
            loadFeedbacks('all');
        }
    } else if (viewName === 'users') {
        const view = document.getElementById('view-users');
        if(view) {
            view.style.display = 'block';
            loadUsers();
        }
    } else if (viewName === 'prompts') {
        const view = document.getElementById('view-prompts');
        if(view) {
            view.style.display = 'flex';
            loadPrompts();
        }
    } else if (viewName === 'knowledge') {
        const view = document.getElementById('view-knowledge');
        if(view) {
            view.style.display = 'block';
            loadKnowledgeBase();
        }
    }
}

// 仪表盘逻辑变量
let currentPage = 1;
const pageSize = 9;
let currentFilter = 'all';
let feedbackSearchKeyword = '';
let selectedFeedbackIds = new Set();

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    const lastView = localStorage.getItem('currentAdminView') || 'chart-dashboard';
    switchView(lastView, null);

    window.addEventListener('resize', resizeCharts);

    const dropZone = document.getElementById('upload-zone');
    if(dropZone) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {e.preventDefault(); e.stopPropagation();}, false);
        });
        dropZone.addEventListener('dragover', () => dropZone.classList.add('dragover'));
        dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
        dropZone.addEventListener('drop', (e) => {
            dropZone.classList.remove('dragover');
            handleFiles(e.dataTransfer.files);
        });
    }
});
function loadStats() {
    fetch('/api/admin/stats').then(r => r.json()).then(data => {
        document.getElementById('stats-box').innerHTML = `
            <div class="card"><h3>总用户</h3><div class="num">${data.users}</div></div>
            <div class="card"><h3>总对话</h3><div class="num">${data.messages}</div></div>
            <div class="card"><h3 style="color:#4caf50;">👍 点赞</h3><div class="num" style="color:#4caf50;">${data.likes}</div></div>
            <div class="card"><h3 style="color:#ef4444;">👎 点踩</h3><div class="num" style="color:#ef4444;">${data.dislikes}</div></div>
        `;
    });
}
function loadFeedbacks(type, btn) {
    if (type !== currentFilter) {
        currentPage = 1;
        currentFilter = type;
    }
    if (btn) {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    }

    const tbody = document.getElementById('feedback-table');
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:30px;">加载中...</td></tr>';

    // 获取搜索关键词
    feedbackSearchKeyword = document.getElementById('feedback-search')?.value.trim() || '';

    fetch(`/api/admin/feedbacks?filter_type=${currentFilter}&page=${currentPage}&size=${pageSize}&search=${encodeURIComponent(feedbackSearchKeyword)}`)
        .then(r => r.json())
        .then(data => {
            let list = data.items || data || [];
            let total = data.total || list.length;
            renderPagination(total);
            renderTable(list);
        });
}
function handleFeedbackSearch(event) {
    const input = document.getElementById('feedback-search');
    feedbackSearchKeyword = input ? input.value.trim() : '';

    if (!event || event.type === 'click' || event.key === 'Enter') {
        currentPage = 1;
        loadFeedbacks(currentFilter);
    }
}
function resetFeedbackSearch() {
    const input = document.getElementById('feedback-search');
    if (input) input.value = '';
    feedbackSearchKeyword = '';
    currentPage = 1;
    loadFeedbacks(currentFilter);
}
function toggleSelectAllFeedback(checkbox) {
    const checkboxes = document.querySelectorAll('.feedback-checkbox');
    checkboxes.forEach(cb => {
        cb.checked = checkbox.checked;
        const id = String(cb.value);
        if (checkbox.checked) {
            selectedFeedbackIds.add(id);
        } else {
            selectedFeedbackIds.delete(id);
        }
    });

    checkbox.indeterminate = false;
    updateFeedbackDeleteBtn();
}
function renderTable(list) {
    const tbody = document.getElementById('feedback-table');
    if (!list || list.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:30px; color:#666;">暂无数据</td></tr>';
        selectedFeedbackIds.clear();
        updateFeedbackDeleteBtn();
        return;
    }

    // 更新全选状态
    const allChecked = list.length > 0 && list.every(item => selectedFeedbackIds.has(String(item.id)));
    document.getElementById('select-all-feedback').checked = allChecked;

    tbody.innerHTML = list.map(item => {
        const badgeClass = item.feedback === 1 ? 'badge-green' : (item.feedback === -1 ? 'badge-red' : 'badge');
        const badgeText = item.feedback === 1 ? '好评' : (item.feedback === -1 ? '差评' : '咨询');
        const isChecked = selectedFeedbackIds.has(String(item.id));
        return `
        <tr ondblclick="openDetail(${item.id})" style="cursor: pointer;">
            <td class="checkbox-col"><input type="checkbox" class="feedback-checkbox" value="${item.id}" 
                 ${isChecked ? 'checked' : ''} 
                 onchange="event.stopPropagation(); toggleFeedbackSelection(this, ${item.id})"></td>
            <td class="col-user" title="${item.username}">${item.username}</td>
            <td class="col-query" title="${item.user_query}">${item.user_query}</td>
            <td class="col-reply" title="${item.ai_reply}">${item.ai_reply}</td>
            <td class="col-time">${item.time}</td>
            <td class="col-status"><span class="badge ${badgeClass}">${badgeText}</span></td>
        </tr>`;
    }).join('');
    
    // 渲染后更新删除按钮状态
    updateFeedbackDeleteBtn();
}
function toggleFeedbackSelection(checkbox, id) {
    const idStr = String(id);
    if (checkbox.checked) {
        selectedFeedbackIds.add(idStr);
    } else {
        selectedFeedbackIds.delete(idStr);
    }
    updateSelectAllState();
    updateFeedbackDeleteBtn();
}
function renderPagination(totalCount) {
    const totalPages = Math.ceil(totalCount / pageSize) || 1;
    document.getElementById('page-stats').innerText = `共 ${totalCount} 条数据`;
    document.getElementById('curr-page-num').innerText = currentPage;
    document.getElementById('total-page-num').innerText = totalPages;
    document.getElementById('prev-btn').disabled = (currentPage <= 1);
    document.getElementById('next-btn').disabled = (currentPage >= totalPages);
}
function updateSelectAllState() {
    const checkboxes = document.querySelectorAll('.feedback-checkbox');
    const allChecked = checkboxes.length > 0 && 
                      Array.from(checkboxes).every(cb => cb.checked);
    const someChecked = Array.from(checkboxes).some(cb => cb.checked);
    
    const selectAll = document.getElementById('select-all-feedback');
    if (selectAll) {
        selectAll.checked = allChecked;
        selectAll.indeterminate = someChecked && !allChecked;
    }
}
function updateFeedbackDeleteBtn() {
    const deleteBtn = document.getElementById('delete-feedback-btn');
    if (!deleteBtn) return;
    
    if (selectedFeedbackIds.size > 0) {
        deleteBtn.style.display = 'flex';
        deleteBtn.innerHTML = `<i class="fa-solid fa-trash"></i> 删除选中 (${selectedFeedbackIds.size})`;
    } else {
        deleteBtn.style.display = 'none';
    }
}
// 删除选中的反馈
async function deleteSelectedFeedbacks() {
    if (selectedFeedbackIds.size === 0) {
        Swal.fire({
            title: '提示',
            text: '请先选择要删除的反馈',
            icon: 'info',
            background: '#1e1e1e',
            color: '#fff'
        });
        return;
    }
    
    const result = await Swal.fire({
        title: '确认删除',
        text: `确定要删除选中的 ${selectedFeedbackIds.size} 条反馈吗？此操作不可恢复！`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#ef4444',
        cancelButtonColor: '#666',
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        background: '#1e1e1e',
        color: '#fff'
    });
    
    if (result.isConfirmed) {
        try {
            Swal.showLoading();
            const messageIds = Array.from(selectedFeedbackIds).map(id => parseInt(id));
            const response = await fetch('/api/admin/feedbacks', {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ message_ids: messageIds })
            });
            
            let data;
            try {
                data = await response.json();
            } catch (e) {
                data = { detail: '服务器返回格式错误' };
            }
            
            if (response.ok) {
                Swal.fire({
                    title: '删除成功',
                    text: data.msg || `已删除 ${selectedFeedbackIds.size} 条反馈`,
                    icon: 'success',
                    timer: 1500,
                    showConfirmButton: false,
                    background: '#1e1e1e',
                    color: '#fff'
                });
                selectedFeedbackIds.clear();
                updateFeedbackDeleteBtn();
                loadFeedbacks(currentFilter);
            } else {
                const errorMsg = data.detail || data.msg || data.message || '删除操作失败';
                Swal.fire({
                    title: '删除失败',
                    text: typeof errorMsg === 'string' ? errorMsg : JSON.stringify(errorMsg),
                    icon: 'error',
                    background: '#1e1e1e',
                    color: '#fff'
                });
            }
        } catch (error) {
            Swal.fire({
                title: '网络错误',
                text: error.message || '无法连接到服务器',
                icon: 'error',
                background: '#1e1e1e',
                color: '#fff'
            });
        }
    }
}
function changePage(d) {
    currentPage += d;
    loadFeedbacks(currentFilter);
}

// 打开反馈详情
function openDetail(msgId) {
    const modal = document.getElementById('detail-modal');
    const container = document.getElementById('modal-chat-container');
    modal.style.display = 'flex';
    container.innerHTML = '加载中...';
    fetch(`/api/admin/message/${msgId}/details`).then(r => r.json()).then(data => {
        if (data.error) {
            container.innerText = "加载失败";
            return;
        }
        container.innerHTML = data.chat_history.map(msg => `
            <div class="chat-row ${msg.role === 'user' ? 'chat-user' : 'chat-ai'}">
                <div class="chat-role">${msg.role} - ${msg.time}</div>
                <div class="chat-bubble ${msg.is_target ? 'target-msg' : ''}">${escapeHtml(msg.content)}</div>
            </div>`).join('');
        setTimeout(() => {
            const t = container.querySelector('.target-msg');
            if (t) t.scrollIntoView({block: "center"});
        }, 100);
    });
}

// 模态框点击外部关闭（延迟绑定，确保 DOM 已加载）
document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('feedback-search');
    if (searchInput) {
        searchInput.addEventListener('keyup', function(event) {
            if (event.key === 'Enter') {
                handleFeedbackSearch(event);
            }
        });
        
        const searchButton = searchInput.nextElementSibling;
        if (searchButton && searchButton.classList.contains('search-btn')) {
            searchButton.addEventListener('click', handleFeedbackSearch);
        }
    }
});

function escapeHtml(text) {
    return text ? text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") : "";
}

// 提示词工程相关
const PROMPT_NAMES = {
    "SAFETY_CHECK_PROMPT": "安全审核",
    "BLOCK_RESPONSE_TEXT": "拦截回复语",
    "INTENT_CLASSIFY_PROMPT": "意图分类",
    "QUERY_OPTIMIZE_PROMPT": "关键词提取",
    "DATA_FILTER_PROMPT": "资料清洗",
    "DOCTOR_SYSTEM_PROMPT": "医生人设 (System)",
    "DOCTOR_USER_PROMPT": "用户指令 (User)",
    "NO_DATA_RESPONSE_TEXT": "无资料默认回复"
};

let currentPromptKey = null;
let currentChainLogs = [];
let displayedChainLogIndices = [];

// 加载提示词列表
async function loadPrompts() {
    try {
        const res = await fetch('/api/admin/prompts');
        const data = await res.json();
        const container = document.getElementById('prompt-list');
        container.innerHTML = '';

        for (const [key, content] of Object.entries(data)) {
            const div = document.createElement('div');
            div.className = 'prompt-item';
            if (key === currentPromptKey) div.classList.add('active');
            const cnName = PROMPT_NAMES[key] || key;
            div.innerHTML = `
                <div class="prompt-key" style="font-size:14px; color:#fff;">${cnName}</div>
                <div style="font-size:11px; color:#666; margin-bottom:5px;">${key}</div>
                <div class="prompt-desc">${content.split('\n')[0]}</div>
            `;
            div.onclick = () => selectPrompt(key, content, div);
            container.appendChild(div);
        }
    } catch (e) { console.error(e); }
}

// 选中提示词
function selectPrompt(key, content, el) {
    currentPromptKey = key;
    document.querySelectorAll('.prompt-item').forEach(e => e.classList.remove('active'));
    el.classList.add('active');
    document.getElementById('current-key').innerText = `${PROMPT_NAMES[key] || key} (${key})`;
    const tx = document.getElementById('prompt-editor');
    tx.value = content;
    tx.disabled = false;
    document.getElementById('save-btn').disabled = false;
    document.getElementById('save-status').style.display = 'none';
}

// 保存提示词
async function savePrompt() {
    if (!currentPromptKey) return;
    const btn = document.getElementById('save-btn');
    const originalText = btn.innerHTML;
    btn.innerHTML = '保存中...';
    btn.disabled = true;
    try {
        const res = await fetch('/api/admin/prompts', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({key: currentPromptKey, content: document.getElementById('prompt-editor').value})
        });
        if (res.ok) {
            const s = document.getElementById('save-status');
            s.style.display = 'inline';
            setTimeout(() => s.style.display = 'none', 3000);
        } else alert("保存失败");
    } catch (e) { alert("请求出错"); }
    btn.innerHTML = originalText;
    btn.disabled = false;
}

// 运行全链路仿真
async function runChainTest() {
    const query = document.getElementById('chain-query').value.trim();
    if (!query) { alert("请输入测试问题"); return; }

    const btn = document.getElementById('run-chain-btn');
    const listContainer = document.getElementById('chain-list');
    btn.innerHTML = '仿真中...';
    btn.disabled = true;
    listContainer.innerHTML = '<div style="text-align:center; padding:20px; color:#666;">正在思考...</div>';

    try {
        const res = await fetch('/api/admin/test_rag_chain', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                query: query,
                override_key: currentPromptKey,
                override_content: document.getElementById('prompt-editor').value
            })
        });
        const data = await res.json();
        currentChainLogs = data.logs || [];
        renderChainList(currentChainLogs);
        if (displayedChainLogIndices.length > 0) showStepDetail(displayedChainLogIndices.length - 1);
    } catch (e) {
        listContainer.innerHTML = `<div style="padding:15px; color:#f44336">请求失败: ${e}</div>`;
    } finally {
        btn.innerHTML = '<i class="fa-solid fa-play"></i> 运行仿真';
        btn.disabled = false;
    }
}

// 渲染仿真步骤列表
function renderChainList(logs) {
    const container = document.getElementById('chain-list');
    if (logs.length === 0) {
        container.innerHTML = '<div style="padding:20px; text-align:center; color:#666">无日志</div>';
        displayedChainLogIndices = [];
        return;
    }

    displayedChainLogIndices = logs
        .map((log, index) => ({ log, index }))
        .filter(({ log }) => log.step !== '关键词提取')
        .map(({ index }) => index);

    container.innerHTML = displayedChainLogIndices.map((realIndex, viewIndex) => {
        const log = logs[realIndex];
        let statusColor = log.status === 'success' ? 'success' : (log.status === 'danger' ? 'danger' : (log.status === 'warning' ? 'warning' : 'info'));
        return `
            <div class="step-item" id="step-${viewIndex}" onclick="showStepDetail(${viewIndex})">
                <div class="step-head">
                    <div style="display:flex; align-items:center;">
                        <span class="status-dot ${statusColor}"></span>
                        <span class="step-name">${log.step}</span>
                    </div>
                    <span class="step-time">${log.time}</span>
                </div>
                <div class="step-preview">${escapeHtml(log.preview || '点击查看详情')}</div>
            </div>
        `;
    }).join('');
}

// 显示仿真步骤详情
function showStepDetail(index) {
    const realIndex = displayedChainLogIndices[index];
    const log = currentChainLogs[realIndex];
    if (!log) return;

    document.querySelectorAll('.step-item').forEach(el => el.classList.remove('active'));
    const activeItem = document.getElementById(`step-${index}`);
    if (activeItem) {
        activeItem.classList.add('active');

        // 禁用滚动动画，避免触发布局抖动
        const container = document.getElementById('chain-list');
        const containerRect = container.getBoundingClientRect();
        const itemRect = activeItem.getBoundingClientRect();

        // 如果选中项在可视区上方/下方，直接调整 container.scrollTop（无动画）
        if (itemRect.top < containerRect.top) {
            container.scrollTop -= (containerRect.top - itemRect.top) + 8;
        } else if (itemRect.bottom > containerRect.bottom) {
            container.scrollTop += (itemRect.bottom - containerRect.bottom) + 8;
        }
    }

    document.getElementById('detail-title').innerText = log.title || log.step;
    document.getElementById('detail-time').innerText = `耗时: ${log.time}`;
    const contentBox = document.getElementById('detail-content');
    contentBox.innerText = log.output || '';
    contentBox.scrollTop = 0;
}

// 知识库管理逻辑
function handleFileSelect(input) { handleFiles(input.files); }

// 上传文件逻辑 (支持串行上传 + 自动轮询)
async function handleFiles(files) {
    if (files.length === 0) return;

    // 1. 锁定按钮状态
    const btn = document.querySelector('#upload-zone button');
    const originalText = btn.innerText;
    btn.innerText = "正在上传...";
    btn.disabled = true;

    let successCount = 0;
    let failCount = 0;

    // 2. 遍历文件，逐个发送请求 (串行上传)
    for (let i = 0; i < files.length; i++) {
        const file = files[i];

        const formData = new FormData();
        formData.append('file', file);

        try {
            // 更新按钮提示，显示进度
            btn.innerText = `上传中 (${i + 1}/${files.length})...`;

            const response = await fetch('/api/knowledge/upload', {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                successCount++;
            } else {
                const err = await response.json();
                console.error(`文件 ${file.name} 上传失败:`, err);
                failCount++;
            }
        } catch (error) {
            console.error(`网络错误:`, error);
            failCount++;
        }
    }

    // 3. 恢复状态并通知结果
    btn.innerText = originalText;
    btn.disabled = false;
    document.getElementById('file-input').value = ''; // 清空选择框

    if (successCount > 0 || failCount > 0) {
        let msg = `上传结束：成功 ${successCount} 个`;
        if (failCount > 0) msg += `，失败 ${failCount} 个`;

        // 简单提示
        Swal.fire({
            title: '上传完成',
            text: msg,
            icon: failCount > 0 ? 'warning' : 'success',
            timer: 1500,
            showConfirmButton: false,
            background: '#1e1e1e', color: '#fff'
        });

        // 成功后启动轮询
        // 只要有成功的（哪怕1个），就意味着后台有任务在跑，需要轮询状态
        if (successCount > 0) {
            startPollingStatus();
        }
    }
}

let pollingInterval = null;

function startPollingStatus() {
    loadKnowledgeBase();

    if (pollingInterval) clearInterval(pollingInterval);

    let checkCount = 0;

    pollingInterval = setInterval(async () => {
        checkCount++;

        const isAllDone = await checkAllFilesDone();

        if (isAllDone || checkCount > 60) {
            clearInterval(pollingInterval);
            pollingInterval = null;
            if (isAllDone) {
                console.log("所有文件处理完毕，停止轮询");
                loadKnowledgeBase();
            }
        } else {

            loadKnowledgeBase();
        }
    }, 1500);
}

// 辅助函数：检查列表里是否还有 processing 的文件
async function checkAllFilesDone() {
    try {
        const res = await fetch(`/api/knowledge/list?page=${kbCurrentPage}&size=${kbPageSize}`);
        const data = await res.json();
        // 只要有一个文件的状态是 processing，就返回 false (表示还没 Done)
        const hasProcessing = data.files.some(f => f.status === 'processing');
        return !hasProcessing;
    } catch (e) {
        return true;
    }
}

let kbCurrentPage = 1;
const kbPageSize = 8;
let selectedDocIds = new Set();

async function loadKnowledgeBase() {
    const tbody = document.getElementById('kb-table-body');

    try {
        const res = await fetch(`/api/knowledge/list?page=${kbCurrentPage}&size=${kbPageSize}`);
        const data = await res.json();

        selectedDocIds.clear();
        updateBatchToolbar();
        const selectAllBox = document.getElementById('select-all');
        if(selectAllBox) selectAllBox.checked = false;

        document.getElementById('kb-doc-count').innerText = data.total_docs || 0;
        document.getElementById('kb-chunk-count').innerText = data.total_chunks || 0;
        renderKbPagination(data.total_docs);

        const list = data.files || [];
        if (list.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:30px; color:#666;">暂无文档</td></tr>';
            return;
        }

        tbody.innerHTML = list.map(file => {
            const isArchived = file.status === 'archived';
            return `
            <tr>
                <td class="checkbox-col">
                    <input type="checkbox" class="doc-checkbox" value="${file.id}" onchange="toggleSelectDoc('${file.id}')">
                </td>
                <td><i class="fa-regular fa-file-lines" style="margin-right:8px; color:#9ca3af;"></i>${file.filename}</td>
                <td style="color:#666;">${formatSize(file.size)}</td>
                <td>${file.chunks_count}</td>
                <td>${getStatusBadge(file.status)}</td>
                <td>
                    <div class="action-btn-group">
                        ${!isArchived ? 
                          `<button class="btn-fixed btn-purple" onclick="toggleArchive('${file.id}', true)">
                             <i class="fa-solid fa-box-archive" style="margin-right:5px"></i> 归档
                           </button>` : 
                          `<button class="btn-fixed btn-blue" onclick="toggleArchive('${file.id}', false)">
                             <i class="fa-solid fa-box-open" style="margin-right:5px"></i> 启用
                           </button>`
                        }
                        <button class="btn-square-danger" onclick="deleteFile('${file.id}')" title="彻底删除">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>`;
        }).join('');
    } catch (e) {
        console.error(e);
        // 只有在真的出错且表格为空时才显示错误提示，防止闪烁
        if(tbody.innerHTML.includes('加载中') || tbody.innerHTML === '') {
            tbody.innerHTML = '<tr><td colspan="6" style="color:red; text-align:center;">加载失败</td></tr>';
        }
    }
}

// 知识库选择逻辑
function toggleSelectDoc(id) {
    id = String(id);
    if (selectedDocIds.has(id)) selectedDocIds.delete(id);
    else selectedDocIds.add(id);
    updateBatchToolbar();
}

function toggleSelectAll(checkbox) {
    document.querySelectorAll('.doc-checkbox').forEach(cb => {
        cb.checked = checkbox.checked;
        if (checkbox.checked) selectedDocIds.add(cb.value);
        else selectedDocIds.delete(cb.value);
    });
    updateBatchToolbar();
}

function updateBatchToolbar() {
    const count = selectedDocIds.size;
    document.getElementById('selected-count').innerText = count;
    const toolbar = document.getElementById('batch-toolbar');
    if (count > 0) toolbar.classList.add('show');
    else toolbar.classList.remove('show');
}

async function batchAction(type) {
    const ids = Array.from(selectedDocIds).map(Number);
    if (ids.length === 0) return;
    let url, method, body, title, text, color;

    if (type === 'archive') {
        url = '/api/knowledge/batch/status'; method = 'PUT'; body = { ids: ids, status: 'archived' };
        title = `归档 ${ids.length} 个文件？`; text = "归档后将不再参与检索。"; color = '#6b7280';
    } else if (type === 'enable') {
        url = '/api/knowledge/batch/status'; method = 'PUT'; body = { ids: ids, status: 'success' };
        title = `启用 ${ids.length} 个文件？`; text = "启用后将恢复检索。"; color = '#3b82f6';
    } else if (type === 'delete') {
        url = '/api/knowledge/batch/delete'; method = 'DELETE'; body = { ids: ids };
        title = `彻底删除 ${ids.length} 个文件？`; text = "删除后不可恢复！"; color = '#ef4444';
    }

    Swal.fire({
        title: title, text: text, icon: type === 'delete' ? 'warning' : 'question',
        showCancelButton: true, confirmButtonColor: color, confirmButtonText: '确定执行', cancelButtonText: '取消',
        background: '#1e1e1e', color: '#fff'
    }).then(async (result) => {
        if (result.isConfirmed) {
            Swal.showLoading();
            try {
                const res = await fetch(url, {
                    method: method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
                });
                const data = await res.json();
                if (res.ok) {
                    Swal.fire({icon: 'success', title: '操作成功', text: data.msg, timer: 1500, showConfirmButton: false, background: '#1e1e1e', color: '#fff'});
                    loadKnowledgeBase();
                } else Swal.fire('失败', data.msg, 'error');
            } catch (e) { Swal.fire('错误', '网络请求失败', 'error'); }
        }
    });
}

// 知识库分页
function renderKbPagination(totalCount) {
    const totalPages = Math.ceil(totalCount / kbPageSize) || 1;
    document.getElementById('kb-page-stats').innerText = `共 ${totalCount} 条数据`;
    document.getElementById('kb-curr-page').innerText = kbCurrentPage;
    document.getElementById('kb-total-page').innerText = totalPages;
    document.getElementById('kb-prev-btn').disabled = (kbCurrentPage <= 1);
    document.getElementById('kb-next-btn').disabled = (kbCurrentPage >= totalPages);
}

function changeKbPage(delta) {
    kbCurrentPage += delta;
    loadKnowledgeBase();
}

// 用户管理分页
function changeUserPage(delta) {
    userPage += delta;
    loadUsers();
}
async function loadChartDashboard() {
    try {
        // 并行请求统计数据和图表数据
        const [stats, charts] = await Promise.all([
            fetch('/api/admin/stats').then(r => r.json()),
            fetch('/api/admin/dashboard/charts').then(r => r.json())
        ]);

        // 1. 渲染顶部数字卡片
        const statsBox = document.getElementById('stats-box-new');
        statsBox.innerHTML = `
            <div class="card"><h3>👥 总用户</h3><div class="num">${stats.users}</div></div>
            <div class="card"><h3>🗨️ 总消息</h3><div class="num">${stats.messages}</div></div>
            <div class="card"><h3 style="color:#4caf50;">👍 好评</h3><div class="num" style="color:#4caf50;">${stats.likes}</div></div>
            <div class="card"><h3 style="color:#ef4444;">👎 差评</h3><div class="num" style="color:#ef4444;">${stats.dislikes}</div></div>
        `;

        // 2. 渲染图表
        renderFeedbackPie(charts.feedback_chart);
        renderRiskBar(charts.risk_user_chart);
        renderSpeedGauge(charts.avg_response_time);

    } catch (e) {
        console.error("加载图表失败:", e);
    }
}

function initChart(domId) {
    if (!chartInstances[domId]) {
        chartInstances[domId] = echarts.init(document.getElementById(domId), null, {
            renderer: 'canvas',
            backgroundColor: 'transparent'
        });
    }
    return chartInstances[domId];
}

function renderFeedbackPie(data) {
    const chart = initChart('chart-feedback');
    chart.setOption({
        tooltip: { 
            trigger: 'item',
            backgroundColor: 'rgba(30, 30, 30, 0.9)',
            borderColor: '#333',
            textStyle: {
                color: '#e3e3e3'
            }
        },
        legend: { 
            bottom: '0%', 
            left: 'center',
            textStyle: { 
                color: '#e3e3e3' 
            },
            icon: 'circle',
            itemWidth: 8,
            itemHeight: 8,
            itemGap: 20
        },
        color: ['#4CAF50', '#FFC107', '#9E9E9E'], // Green, Amber, Grey
        series: [{
            type: 'pie',
            radius: ['40%', '70%'],
            center: ['50%', '45%'],
            avoidLabelOverlap: false,
            itemStyle: { 
                borderRadius: 4, 
                borderColor: '#1e1e1e', 
                borderWidth: 2
            },
            label: { 
                show: false,
                color: '#e3e3e3'
            },
            emphasis: {
                label: {
                    show: true,
                    fontSize: '16',
                    fontWeight: 'bold',
                    color: '#e3e3e3'
                }
            },
            labelLine: {
                show: false
            },
            data: data.map(item => {
                // Map the data to ensure consistent ordering
                const nameMap = {
                    '好评': { color: '#4CAF50', name: '好评' },
                    '差评': { color: '#FFC107', name: '差评' },
                    '普通咨询': { color: '#9E9E9E', name: '普通咨询' }
                };
                return {
                    ...item,
                    itemStyle: { color: nameMap[item.name]?.color || '#9E9E9E' }
                };
            })
        }]
    });
}

function renderRiskBar(data) {
    const chart = initChart('chart-risk');
    chart.setOption({
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'shadow'
            },
            backgroundColor: 'rgba(30, 30, 30, 0.9)',
            borderColor: '#333',
            textStyle: {
                color: '#e3e3e3'
            }
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '3%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            data: data.usernames,
            axisLine: {
                lineStyle: {
                    color: '#555'
                }
            },
            axisLabel: {
                color: '#aaa',
                rotate: 30,
                fontSize: 12
            }
        },
        yAxis: {
            type: 'value',
            axisLine: {
                show: true,
                lineStyle: {
                    color: '#555'
                }
            },
            splitLine: {
                lineStyle: {
                    color: '#2a2a2a'
                }
            },
            axisLabel: {
                color: '#aaa'
            }
        },
        series: [{
            name: '消极提问次数',
            type: 'bar',
            barWidth: '40%',
            data: data.counts,
            itemStyle: {
                color: '#4a90e2', // Blue color instead of red
                borderRadius: [4, 4, 0, 0]
            },
            label: {
                show: true,
                position: 'top',
                color: '#e3e3e3',
                formatter: '{c}'
            }
        }]
    });
}

function renderSpeedGauge(value) {
    const chart = initChart('chart-speed');
    chart.setOption({
        tooltip: {
            formatter: '平均响应时间: {c} 秒',
            backgroundColor: 'rgba(30, 30, 30, 0.9)',
            borderColor: '#333',
            textStyle: {
                color: '#e3e3e3'
            }
        },
        series: [{
            type: 'gauge',
            progress: {
                show: true,
                width: 12,
                itemStyle: {
                    color: {
                        type: 'linear',
                        x: 0,
                        y: 0,
                        x2: 1,
                        y2: 0,
                        colorStops: [{
                            offset: 0, color: '#4CAF50' // Green
                        }, {
                            offset: 0.7, color: '#FFC107' // Amber
                        }, {
                            offset: 1, color: '#F44336' // Red
                        }]
                    }
                }
            },
            axisLine: {
                lineStyle: {
                    width: 12,
                    color: [
                        [0.3, '#4CAF50'],
                        [0.7, '#FFC107'],
                        [1, '#F44336']
                    ]
                }
            },
            axisTick: {
                show: false
            },
            splitLine: {
                distance: -12,
                length: 12,
                lineStyle: {
                    width: 2,
                    color: '#333'
                }
            },
            axisLabel: {
                distance: 8,
                color: '#aaa',
                fontSize: 12
            },
            anchor: {
                show: true,
                showAbove: true,
                size: 16,
                itemStyle: {
                    color: '#4a90e2'
                }
            },
            title: {
                show: true,
                color: '#aaa',
                fontSize: 12,
                offsetCenter: [0, '75%']
            },
            detail: {
                valueAnimation: true,
                fontSize: 24,
                offsetCenter: [0, '35%'],
                color: '#e3e3e3',
                formatter: '{value} s'
            },
            data: [{
                value: value || 0,
                name: '平均响应时间'
            }]
        }]
    });
}

function resizeCharts() {
    Object.values(chartInstances).forEach(c => c.resize());
}
// 删除单个文件
function deleteFile(fileId) {
    Swal.fire({
        title: '危险操作', text: "这将彻底删除文件及其所有向量数据，无法恢复！", icon: 'warning',
        showCancelButton: true, confirmButtonColor: '#ef4444', cancelButtonColor: '#666',
        confirmButtonText: '彻底删除', cancelButtonText: '取消', background: '#1e1e1e', color: '#fff'
    }).then(async (result) => {
        if (result.isConfirmed) {
            try {
                Swal.showLoading();
                const res = await fetch(`/api/knowledge/file/${fileId}`, { method: 'DELETE' });
                if (res.ok) {
                    Swal.fire({title: '已删除!', icon: 'success', timer: 1500, showConfirmButton: false, background: '#1e1e1e', color: '#fff'});
                    loadKnowledgeBase();
                } else Swal.fire('删除失败', '后端返回错误', 'error');
            } catch (e) { Swal.fire('网络错误', '无法连接服务器', 'error'); }
        }
    });
}

// 状态徽章辅助函数
function getStatusBadge(status) {
    if (status === 'indexed' || status === 'success' || status === 'completed') return '<span class="status-badge status-success"><i class="fa-solid fa-check"></i> 已索引</span>';
    if (status === 'processing') return '<span class="status-badge status-processing"><i class="fa-solid fa-spinner fa-spin"></i> 处理中</span>';
    if (status === 'archived') return '<span class="status-badge status-archived"><i class="fa-solid fa-box-archive"></i> 已归档</span>';
    return `<span class="status-badge status-error">失败 (${status})</span>`;
}

function formatSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 归档/启用文件
function toggleArchive(fileId, doArchive) {
    const actionText = doArchive ? '归档' : '启用';
    const confirmColor = doArchive ? '#f59e0b' : '#3b82f6';
    Swal.fire({
        title: `确定要${actionText}吗？`,
        text: doArchive ? "归档后，RAG 系统将不会搜索到该文档的内容。" : "启用后，该文档将重新加入知识库搜索范围。",
        icon: 'question', showCancelButton: true, confirmButtonColor: confirmColor, cancelButtonColor: '#666',
        confirmButtonText: `确定${actionText}`, cancelButtonText: '取消', background: '#1e1e1e', color: '#fff'
    }).then(async (result) => {
        if (result.isConfirmed) {
            try {
                Swal.showLoading();
                const res = await fetch(`/api/knowledge/file/${fileId}/status`, {
                    method: 'PUT', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ status: doArchive ? 'archived' : 'success' })
                });
                if (res.ok) {
                    Swal.fire({title: '操作成功!', text: `文件已${actionText}`, icon: 'success', timer: 1500, showConfirmButton: false, background: '#1e1e1e', color: '#fff'});
                    loadKnowledgeBase();
                } else Swal.fire('操作失败', '请检查后端日志', 'error');
            } catch (e) { Swal.fire('网络错误', e.message, 'error'); }
        }
    });
}
let userPage = 1;
const userPageSize = 10;

function loadUsers() {
    const tbody = document.getElementById('users-table-body');
    if(!tbody) return;

    fetch(`/api/admin/users?page=${userPage}&size=${userPageSize}`)
        .then(r => r.json())
        .then(data => {
            const totalPages = Math.ceil(data.total / userPageSize) || 1;
            
            // 修复：如果当前页超过总页数，重置为最后一页
            if (userPage > totalPages && totalPages > 0) {
                userPage = totalPages;
                loadUsers();
                return;
            }
            
            document.getElementById('user-page-stats').innerText = `共 ${data.total} 人`;
            document.getElementById('user-curr-page').innerText = userPage;
            document.getElementById('user-total-page').innerText = totalPages;
            document.getElementById('user-prev-btn').disabled = (userPage <= 1);
            document.getElementById('user-next-btn').disabled = (userPage >= totalPages);

            tbody.innerHTML = data.items.map(u => {
                const isSelf = u.username === 'admin';
                // 头像说明：数据库中的 avatar_url 字段如果为空，前端会自动生成彩色首字母圆形头像
                // 生成逻辑：根据用户ID计算HSL颜色值，确保每个用户有不同颜色的头像
                const firstLetter = u.username.charAt(0).toUpperCase();
                const avatarColor = `hsl(${(u.id * 137.508) % 360}, 50%, 50%)`;
                const defaultAvatar = `data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><circle cx="16" cy="16" r="16" fill="${avatarColor}"/><text x="16" y="22" text-anchor="middle" fill="#fff" font-size="14" font-weight="600">${firstLetter}</text></svg>`)}`;
                // 如果数据库中没有头像URL，直接使用生成的默认头像
                const avatarUrl = (u.avatar && u.avatar.trim() && u.avatar !== '') ? u.avatar : defaultAvatar;
                return `
                <tr>
                    <td>${u.id}</td>
                    <td><img src="${avatarUrl}" class="user-avatar-sm" onerror="this.src='${defaultAvatar}'"> ${u.username}</td>
                    <td><span style="color:${u.role==='管理员'?'#60a5fa':'#ccc'}">${u.role}</span></td>
                    <td>${u.created_at}</td>
                    <td>${u.last_login}</td>
                    <td>
                        <label class="switch">
                            <input type="checkbox" 
                                ${u.is_active ? 'checked' : ''} 
                                ${isSelf ? 'disabled' : ''}
                                onchange="toggleUserStatus(${u.id}, this.checked)">
                            <span class="slider"></span>
                        </label>
                    </td>
                </tr>`;
            }).join('');
        });
}
function toggleUserStatus(userId, isActive) {
    fetch(`/api/admin/users/${userId}/status`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ is_active: isActive })
    })
    .then(r => r.json())
    .then(data => {
        if(data.status === 'ok') {
            const Toast = Swal.mixin({
                toast: true, position: 'top-end', showConfirmButton: false, timer: 3000,
                background: '#1e1e1e', color: '#fff'
            });
            Toast.fire({icon: 'success', title: data.msg});
        } else {
            Swal.fire('Error', data.detail || '操作失败', 'error');
            loadUsers(); // 失败回滚状态
        }
    });
}
// 退出登录
function handleAdminLogout() {
    Swal.fire({
        title: '确定要退出吗？', text: "这将清除您的登录状态并返回首页。", icon: 'question',
        showCancelButton: true, confirmButtonColor: '#3085d6', cancelButtonColor: '#d33',
        confirmButtonText: '退出', cancelButtonText: '取消', background: '#1e1e1e', color: '#fff'
    }).then((result) => {
        if (result.isConfirmed) {
            localStorage.clear();
            document.cookie.split(";").forEach(function(c) {
                document.cookie = c.replace(/^ +/, "").replace(/=.*/, "=;expires=" + new Date().toUTCString() + ";path=/");
            });
            window.location.replace("/");
        }
    });
}