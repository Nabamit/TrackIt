/**
 * TrackIt SPA Engine
 * High-performance vanilla JS state machine, API client, and visual renderer
 */

const API_BASE = '/api';

// Application State
const state = {
    accessToken: localStorage.getItem('accessToken'),
    refreshToken: localStorage.getItem('refreshToken'),
    user: null,
    projects: [],
    tasks: [],
    currentTab: 'dashboard',
    toastTimeout: null
};

// ==============================================================================
// 1. API fetch Client with Auto-Refresh JWT
// ==============================================================================
async function apiFetch(url, options = {}) {
    if (!options.headers) {
        options.headers = {};
    }
    
    // Add bearer token if present
    if (state.accessToken) {
        options.headers['Authorization'] = `Bearer ${state.accessToken}`;
    }
    
    if (!(options.body instanceof FormData) && options.body && typeof options.body === 'object') {
        options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(options.body);
    }

    try {
        let response = await fetch(url, options);
        
        // Handle token expiry (Unauthorized)
        if (response.status === 401 && state.refreshToken) {
            console.log('Access token expired, attempting refresh...');
            const refreshed = await attemptTokenRefresh();
            if (refreshed) {
                // Retry request with new token
                options.headers['Authorization'] = `Bearer ${state.accessToken}`;
                response = await fetch(url, options);
            } else {
                logout();
                throw new Error('Session expired. Please log in again.');
            }
        }
        
        return response;
    } catch (err) {
        console.error('Fetch error:', err);
        showToast(err.message || 'Network request failed', 'danger');
        throw err;
    }
}

async function attemptTokenRefresh() {
    try {
        const response = await fetch(`${API_BASE}/auth/token/refresh/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh: state.refreshToken })
        });
        
        if (response.ok) {
            const data = await response.json();
            state.accessToken = data.access;
            localStorage.setItem('accessToken', data.access);
            return true;
        }
    } catch (e) {
        console.error('Refresh token invocation failed:', e);
    }
    return false;
}

// ==============================================================================
// 2. Authentication Controllers
// ==============================================================================
function showAuthOverlay() {
    document.getElementById('auth-modal-overlay').classList.add('active');
    document.getElementById('app-container').style.display = 'none';
}

function hideAuthOverlay() {
    document.getElementById('auth-modal-overlay').classList.remove('active');
    document.getElementById('app-container').style.display = 'grid';
}

function logout() {
    state.accessToken = null;
    state.refreshToken = null;
    state.user = null;
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    showAuthOverlay();
    showToast('Logged out successfully.', 'success');
}

// Handle login submission
document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;

    const response = await fetch(`${API_BASE}/auth/login/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
    });

    if (response.ok) {
        const data = await response.json();
        state.accessToken = data.access;
        state.refreshToken = data.refresh;
        localStorage.setItem('accessToken', data.access);
        localStorage.setItem('refreshToken', data.refresh);
        
        hideAuthOverlay();
        await initApp();
        showToast('Successfully signed in!', 'success');
    } else {
        const errData = await response.json().catch(() => ({}));
        showToast(errData.detail || 'Invalid username or password.', 'danger');
    }
});

// Handle registration submission
document.getElementById('register-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('reg-username').value;
    const email = document.getElementById('reg-email').value;
    const password = document.getElementById('reg-password').value;
    const password_confirm = document.getElementById('reg-password-confirm').value;
    const timezone = document.getElementById('reg-timezone').value;
    const reset_hour = parseInt(document.getElementById('reg-reset-hour').value);

    if (password !== password_confirm) {
        showToast('Passwords do not match.', 'danger');
        return;
    }

    const response = await fetch(`${API_BASE}/auth/register/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password, password_confirm, timezone, reset_hour })
    });

    if (response.ok) {
        showToast('Registration successful! Please sign in.', 'success');
        // Switch to login form
        document.getElementById('register-form').classList.remove('active');
        document.getElementById('login-form').classList.add('active');
    } else {
        const errData = await response.json();
        let errMsg = 'Registration failed.';
        if (errData.username) errMsg = `Username: ${errData.username[0]}`;
        else if (errData.password) errMsg = `Password: ${errData.password[0]}`;
        else if (errData.password_confirm) errMsg = errData.password_confirm[0];
        showToast(errMsg, 'danger');
    }
});

// Toggle forms
document.getElementById('to-register').addEventListener('click', (e) => {
    e.preventDefault();
    document.getElementById('login-form').classList.remove('active');
    document.getElementById('register-form').classList.add('active');
});

document.getElementById('to-login').addEventListener('click', (e) => {
    e.preventDefault();
    document.getElementById('register-form').classList.remove('active');
    document.getElementById('login-form').classList.add('active');
});

document.getElementById('logout-btn').addEventListener('click', logout);

// ==============================================================================
// 3. UI helpers (Toasts and Tab Navigation)
// ==============================================================================
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <span>${message}</span>
        <button class="toast-close">&times;</button>
    `;
    
    toast.querySelector('.toast-close').addEventListener('click', () => {
        toast.remove();
    });
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Tab navigation handler
document.querySelectorAll('.sidebar-nav .nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        const tab = item.getAttribute('data-tab');
        switchTab(tab);
    });
});

function switchTab(tab) {
    state.currentTab = tab;
    
    // Toggle active classes on sidebar links
    document.querySelectorAll('.sidebar-nav .nav-item').forEach(item => {
        if (item.getAttribute('data-tab') === tab) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    // Toggle active sections
    document.querySelectorAll('.tab-pane').forEach(pane => {
        if (pane.id === `tab-${tab}`) {
            pane.classList.add('active');
        } else {
            pane.classList.remove('active');
        }
    });

    // Reload tab data
    loadTabData(tab);
}

// ==============================================================================
// 4. Data Loading & API Calls
// ==============================================================================
async function loadUserData() {
    const res = await apiFetch(`${API_BASE}/auth/profile/`);
    if (res.ok) {
        state.user = await res.json();
        
        // Update header & profile form
        document.getElementById('header-username').textContent = state.user.username;
        document.getElementById('user-display-name').textContent = state.user.username;
        document.getElementById('avatar-initials').textContent = state.user.username.slice(0, 2).toUpperCase();
        document.getElementById('header-tokens').textContent = state.user.grace_tokens_balance;
        document.getElementById('header-timezone').textContent = `${state.user.timezone} (${state.user.reset_hour}:00 Reset)`;
        
        // Settings form inputs
        document.getElementById('profile-timezone').value = state.user.timezone;
        document.getElementById('profile-reset-hour').value = state.user.reset_hour;
    }
}

async function loadProjects() {
    const res = await apiFetch(`${API_BASE}/projects/`);
    if (res.ok) {
        state.projects = await res.json();
    }
}

async function loadTasks() {
    const res = await apiFetch(`${API_BASE}/tasks/`);
    if (res.ok) {
        state.tasks = await res.json();
    }
}

async function loadTabData(tab) {
    try {
        switch (tab) {
            case 'dashboard':
                await Promise.all([loadUserData(), loadProjects(), loadTasks()]);
                renderDashboard();
                break;
            case 'projects':
                await loadProjects();
                renderProjects();
                break;
            case 'tasks':
                await Promise.all([loadProjects(), loadTasks()]);
                renderTasksBoard();
                break;
            case 'habits':
                await loadTasks();
                renderHabitsTab();
                break;
            case 'analytics':
                await renderAnalyticsTab();
                break;
            case 'ai-copilot':
                await loadTasks();
                populateAICopilotContext();
                break;
            case 'profile':
                await loadUserData();
                break;
        }
    } catch (e) {
        console.error('Failed to load data for tab:', tab, e);
    }
}

// ==============================================================================
// 5. Dashboard Tab Rendering
// ==============================================================================
function renderDashboard() {
    const habits = state.tasks.filter(t => t.type === 'recurring');
    const oneOffs = state.tasks.filter(t => t.type === 'one_off');
    const pendingOneOffs = oneOffs.filter(t => t.status !== 'done');
    
    // Set metric summaries
    document.getElementById('stats-projects-count').textContent = state.projects.length;
    document.getElementById('stats-tasks-count').textContent = pendingOneOffs.length;
    
    // Find best streak
    let bestStreak = 0;
    habits.forEach(h => {
        if (h.longest_streak > bestStreak) {
            bestStreak = h.longest_streak;
        }
    });
    document.getElementById('stats-streak-count').textContent = `${bestStreak} days`;

    // Render Habits sub-list
    const habitsContainer = document.getElementById('dashboard-habits-container');
    if (habits.length === 0) {
        habitsContainer.innerHTML = `
            <div class="loading-state">
                <i class="fa-solid fa-calendar-check text-muted" style="font-size: 2rem; margin-bottom: 8px;"></i>
                <p>No recurring habits created yet.</p>
                <button class="btn btn-outline" style="margin-top: 10px;" onclick="switchTab('habits')">Add Habit</button>
            </div>
        `;
    } else {
        habitsContainer.innerHTML = habits.map(h => {
            const hasCheckedInToday = isCheckedInToday(h);
            return `
                <div class="habit-row-item">
                    <div class="habit-title-col">
                        <h4>${h.title}</h4>
                        <span class="habit-streak-badge ${h.current_streak > 0 ? 'badge-streak-active' : ''}">
                            <i class="fa-solid fa-fire"></i> Streak: ${h.current_streak} days (Best: ${h.longest_streak})
                        </span>
                    </div>
                    <div class="habit-actions">
                        ${hasCheckedInToday ? 
                            `<span class="badge badge-low" style="background: rgba(16, 185, 129, 0.15); color: var(--success); padding: 8px 12px; display: inline-flex; align-items: center; gap: 6px;"><i class="fa-solid fa-circle-check"></i> Checked-In</span>` : 
                            `<button class="btn btn-secondary btn-sm" onclick="checkInHabit(${h.id})"><i class="fa-solid fa-fire-burner"></i> Check-in</button>
                             <button class="btn btn-outline btn-sm" title="Freeze for today" onclick="freezeHabit(${h.id})"><i class="fa-solid fa-snowflake"></i> Freeze</button>`
                        }
                    </div>
                </div>
            `;
        }).join('');
    }

    // Render Blocker Chains
    const blockersContainer = document.getElementById('dashboard-blockers-container');
    const blockedTasks = state.tasks.filter(t => t.depends_on_task && t.status !== 'done');
    
    if (blockedTasks.length === 0) {
        blockersContainer.innerHTML = `
            <div class="loading-state">
                <i class="fa-solid fa-shield-halved text-muted" style="font-size: 2rem; margin-bottom: 8px;"></i>
                <p>Awesome! You have no blocked tasks.</p>
            </div>
        `;
    } else {
        // Resolve prerequisite tasks for quick visual mapping
        blockersContainer.innerHTML = blockedTasks.map(t => {
            const prereq = state.tasks.find(p => p.id === t.depends_on_task);
            if (!prereq) return '';
            
            return `
                <div class="blocker-item">
                    <div>
                        <span class="badge badge-high"><i class="fa-solid fa-lock"></i> Blocked</span>
                        <div class="blocker-task-title" style="margin-top: 6px;">${t.title}</div>
                        <span class="blocker-chain-desc">
                            Prerequisite: <strong style="color: #93c5fd;">${prereq.title}</strong> 
                            (${prereq.status === 'in_progress' ? 'In Progress' : 'Pending'})
                        </span>
                    </div>
                    <div>
                        <button class="btn btn-outline btn-sm" onclick="switchTab('tasks')"><i class="fa-solid fa-arrow-right"></i> Board</button>
                    </div>
                </div>
            `;
        }).join('');
    }

    // Fetch and render dashboard consistency score
    fetchDashboardConsistency();
}

function isCheckedInToday(habit) {
    if (!habit.last_checked_in) return false;
    
    // Check if last checked in date matches today in user's timezone
    const now = new Date();
    // Simple date match
    const dateStr = now.toISOString().split('T')[0];
    return habit.last_checked_in === dateStr;
}

async function checkInHabit(id) {
    const res = await apiFetch(`${API_BASE}/tasks/${id}/check-in/`, { method: 'POST' });
    if (res.ok) {
        showToast('Successfully checked in habit streak!', 'success');
        // Trigger confettis or micro-animations
        await loadTabData('dashboard');
    } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || 'Check-in failed.', 'danger');
    }
}

async function freezeHabit(id) {
    const res = await apiFetch(`${API_BASE}/tasks/${id}/freeze/`, { method: 'POST' });
    if (res.ok) {
        showToast('Consumed 1 Grace Token: Habit streak frozen and saved for today!', 'success');
        await loadTabData('dashboard');
    } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || 'Could not freeze habit. Check token balance.', 'danger');
    }
}

async function fetchDashboardConsistency() {
    const res = await apiFetch(`${API_BASE}/analytics/dashboard/`);
    if (res.ok) {
        const data = await res.json();
        document.getElementById('stats-consistency-score').textContent = `${data.consistency_score}%`;
    }
}

// ==============================================================================
// 6. Projects Tab Rendering
// ==============================================================================
function renderProjects() {
    const container = document.getElementById('projects-list-container');
    if (state.projects.length === 0) {
        container.innerHTML = `
            <div class="loading-state" style="grid-column: 1 / -1;">
                <i class="fa-solid fa-folder-open text-muted" style="font-size: 3rem; margin-bottom: 12px;"></i>
                <p>No projects found. Create a project to start organizing tasks.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = state.projects.map(p => {
        // Calculate task progress percentages
        const pTasks = state.tasks.filter(t => t.project === p.id);
        const doneTasks = pTasks.filter(t => t.status === 'done').length;
        const totalTasks = pTasks.length;
        const progressPct = totalTasks > 0 ? Math.round((doneTasks / totalTasks) * 100) : 0;

        return `
            <div class="project-card glassmorphism">
                <h4>${p.title}</h4>
                <p>${p.description || 'No description provided.'}</p>
                <div style="margin-bottom: 15px;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.82rem; color: var(--text-muted); margin-bottom: 4px;">
                        <span>Tasks Completed: ${doneTasks}/${totalTasks}</span>
                        <span>${progressPct}%</span>
                    </div>
                    <div style="height: 6px; background: rgba(15, 17, 26, 0.6); border-radius: 3px; overflow: hidden;">
                        <div style="width: ${progressPct}%; height: 100%; background: linear-gradient(90deg, var(--primary) 0%, var(--secondary) 100%); transition: width 0.4s;"></div>
                    </div>
                </div>
                <div class="project-meta">
                    <span>Created: ${new Date(p.created_at).toLocaleDateString()}</span>
                    <button class="btn btn-outline btn-sm" style="padding: 4px 8px; font-size: 0.75rem;" onclick="openNewTaskModalWithProject(${p.id})">+ Add Task</button>
                </div>
            </div>
        `;
    }).join('');
}

// ==============================================================================
// 7. Tasks Tab Rendering (Kanban Board)
// ==============================================================================
async function renderTasksBoard() {
    const projectFilter = document.getElementById('task-filter-project');
    const priorityFilter = document.getElementById('task-filter-priority');
    
    // Save selections
    const savedProjVal = projectFilter.value;
    
    // Populate project options
    projectFilter.innerHTML = '<option value="">All Projects</option>' + 
        state.projects.map(p => `<option value="${p.id}">${p.title}</option>`).join('');
    
    projectFilter.value = savedProjVal;

    // Filter tasks
    let filtered = state.tasks.filter(t => t.type === 'one_off'); // Kanban boards are for one-offs
    
    if (projectFilter.value) {
        filtered = filtered.filter(t => t.project === parseInt(projectFilter.value));
    }
    if (priorityFilter.value) {
        filtered = filtered.filter(t => t.priority === priorityFilter.value);
    }

    const pendingContainer = document.getElementById('tasks-pending-container');
    const progressContainer = document.getElementById('tasks-in-progress-container');
    const doneContainer = document.getElementById('tasks-done-container');

    const groups = { pending: [], in_progress: [], done: [] };
    filtered.forEach(t => {
        if (groups[t.status]) {
            groups[t.status].push(t);
        }
    });

    // Update column counters
    document.getElementById('badge-pending').textContent = groups.pending.length;
    document.getElementById('badge-in-progress').textContent = groups.in_progress.length;
    document.getElementById('badge-done').textContent = groups.done.length;

    const renderCard = (t) => {
        const proj = state.projects.find(p => p.id === t.project);
        const blocker = t.depends_on_task ? state.tasks.find(bl => bl.id === t.depends_on_task) : null;
        const isBlocked = blocker && blocker.status !== 'done';
        
        return `
            <div class="task-card" data-task-id="${t.id}" id="task-card-${t.id}">
                <div class="task-card-header">
                    <h5>${t.title}</h5>
                    <span class="badge badge-${t.priority}">${t.priority}</span>
                </div>
                <p>${t.description || 'No description.'}</p>
                
                ${isBlocked ? 
                    `<div class="blocked-indicator" title="Prerequisite task must be completed first">
                        <i class="fa-solid fa-lock"></i> Blocked by: ${blocker.title}
                     </div>` : ''
                }
                
                <!-- ML Prediction Pill -->
                <div class="ml-prediction-container" id="ml-prob-${t.id}" style="margin-top: 10px; font-size: 0.8rem;">
                    <span class="text-muted"><i class="fa-solid fa-microchip"></i> Prediction:</span>
                    <span class="prediction-value text-teal" style="font-weight: 700;">Loading...</span>
                </div>

                <div class="task-card-footer">
                    <span>${proj ? proj.title : 'No Project'}</span>
                    <div style="display: flex; gap: 8px;">
                        <button class="btn btn-outline" style="padding: 4px 8px; font-size: 0.72rem;" onclick="editTask(${t.id})"><i class="fa-solid fa-pen-to-square"></i></button>
                        ${t.status !== 'done' && !isBlocked ? 
                            `<button class="btn btn-secondary" style="padding: 4px 8px; font-size: 0.72rem;" onclick="completeTask(${t.id})"><i class="fa-solid fa-check"></i> Done</button>` : ''
                        }
                    </div>
                </div>
            </div>
        `;
    };

    pendingContainer.innerHTML = groups.pending.map(renderCard).join('');
    progressContainer.innerHTML = groups.in_progress.map(renderCard).join('');
    doneContainer.innerHTML = groups.done.map(renderCard).join('');

    // Fetch predictions asynchronously for each task card to improve performance and prevent rendering lags
    filtered.forEach(t => {
        fetchTaskMLPrediction(t.id);
    });
}

async function fetchTaskMLPrediction(taskId) {
    try {
        const res = await apiFetch(`${API_BASE}/tasks/${taskId}/predict/`);
        if (res.ok) {
            const data = await res.json();
            const container = document.querySelector(`#ml-prob-${taskId} .prediction-value`);
            if (container) {
                let colorClass = 'text-teal';
                if (data.risk_level === 'medium') colorClass = 'text-amber';
                if (data.risk_level === 'high') colorClass = 'text-red';
                
                container.className = `prediction-value ${colorClass}`;
                container.textContent = `${data.success_probability}% success chance (${data.risk_level} risk)`;
                container.parentElement.title = data.insights.join('\n');
            }
        }
    } catch (e) {
        console.error('Prediction failed for task:', taskId, e);
    }
}

async function completeTask(taskId) {
    const res = await apiFetch(`${API_BASE}/tasks/${taskId}/`, {
        method: 'PATCH',
        body: { status: 'done' }
    });
    if (res.ok) {
        showToast('Task completed successfully! Streak preserved.', 'success');
        await loadTasks();
        await renderTasksBoard();
    } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.status ? err.status[0] : 'Failed to complete task.', 'danger');
    }
}

// Filter listeners
document.getElementById('task-filter-project').addEventListener('change', renderTasksBoard);
document.getElementById('task-filter-priority').addEventListener('change', renderTasksBoard);

// ==============================================================================
// 8. Habits Tab Rendering
// ==============================================================================
function renderHabitsTab() {
    const container = document.getElementById('habits-detail-container');
    const habits = state.tasks.filter(t => t.type === 'recurring');

    if (habits.length === 0) {
        container.innerHTML = `
            <div class="loading-state" style="grid-column: 1 / -1;">
                <i class="fa-solid fa-fire text-muted" style="font-size: 3rem; margin-bottom: 12px;"></i>
                <p>No habits configured yet. Track daily habits with automatic streak preservation.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = habits.map(h => {
        const hasCheckedInToday = isCheckedInToday(h);
        return `
            <div class="habit-card-detail glassmorphism">
                <h4>${h.title}</h4>
                <p style="color: var(--text-muted); font-size: 0.88rem; flex-grow: 1;">${h.description || 'No description provided.'}</p>
                
                <div class="habit-streaks-row">
                    <div class="streak-score-box">
                        <span>Current Streak</span>
                        <strong>🔥 ${h.current_streak}</strong>
                    </div>
                    <div class="streak-score-box">
                        <span>Longest Streak</span>
                        <strong>🏆 ${h.longest_streak}</strong>
                    </div>
                </div>

                <div style="display: flex; gap: 10px; margin-top: 10px;">
                    ${hasCheckedInToday ? 
                        `<span class="badge badge-low" style="background: rgba(16, 185, 129, 0.15); color: var(--success); padding: 10px; flex-grow: 1; text-align: center;"><i class="fa-solid fa-circle-check"></i> Checked-In Today</span>` : 
                        `<button class="btn btn-secondary" style="flex-grow: 1;" onclick="checkInHabit(${h.id}).then(() => loadTabData('habits'))"><i class="fa-solid fa-fire-burner"></i> Check-in</button>
                         <button class="btn btn-outline" title="Freeze today" onclick="freezeHabit(${h.id}).then(() => loadTabData('habits'))"><i class="fa-solid fa-snowflake"></i></button>`
                    }
                </div>
            </div>
        `;
    }).join('');
}

// ==============================================================================
// 9. Analytics Tab Rendering (Custom SVG Chart drawer)
// ==============================================================================
async function renderAnalyticsTab() {
    const res = await apiFetch(`${API_BASE}/analytics/dashboard/`);
    if (res.ok) {
        const data = await res.json();
        
        // 1. Draw radial progress
        const radius = 40;
        const circumference = 2 * Math.PI * radius; // ~251.2
        const offset = circumference - (data.consistency_score / 100) * circumference;
        
        const radialBar = document.getElementById('analytics-radial-bar');
        radialBar.style.strokeDashoffset = offset;
        document.getElementById('analytics-consistency-pct').textContent = `${data.consistency_score}%`;
        
        // 2. Completion velocity hours
        document.getElementById('analytics-velocity-hours').textContent = `${data.completion_velocity_hours} hrs`;

        // 3. Draw Danger Days Bar Chart (SVG)
        renderDangerDaysSVGChart(data.failure_volatility);
    }
}

function renderDangerDaysSVGChart(volatilityData) {
    const chartContainer = document.getElementById('analytics-danger-chart');
    
    // Display message description
    const alertMsg = document.getElementById('danger-days-message');
    if (volatilityData.danger_day) {
        alertMsg.className = 'alert alert-info';
        alertMsg.textContent = volatilityData.message;
    } else {
        alertMsg.className = 'alert alert-info';
        alertMsg.textContent = "No streak failures recorded yet. Your habits are perfectly consistent!";
    }

    // Generate static weekday labels and mock distribution values for drawing
    // if there is a real danger day.
    const weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
    const maxVal = 100;
    
    let chartHTML = `
        <svg viewBox="0 0 400 200" style="width: 100%; height: 100%;">
    `;
    
    weekdays.forEach((day, index) => {
        const y = 20 + index * 24;
        
        // Compute width based on whether it is the danger day
        let pct = 10; // baseline
        if (volatilityData.danger_day && day === volatilityData.danger_day) {
            pct = volatilityData.percentage;
        } else if (volatilityData.danger_day) {
            // Distribute remaining percentages slightly
            pct = (100 - volatilityData.percentage) / 6;
        } else {
            pct = 0; // no failures
        }
        
        const width = Math.max((pct / maxVal) * 260, 2); // max chart size width
        
        chartHTML += `
            <text x="10" y="${y + 12}" class="chart-label">${day.slice(0, 3)}</text>
            <rect x="50" y="${y}" width="${width}" height="14" rx="4" class="chart-bar" style="fill: ${day === volatilityData.danger_day ? 'var(--priority-high)' : 'var(--primary)'}"></rect>
            <text x="${55 + width}" y="${y + 12}" class="chart-label" style="fill: var(--text-main); font-weight: bold;">${Math.round(pct)}%</text>
        `;
    });
    
    chartHTML += `</svg>`;
    chartContainer.innerHTML = chartHTML;
}

// ==============================================================================
// 10. AI Copilot Panel
// ==============================================================================
function populateAICopilotContext() {
    const select = document.getElementById('copilot-task-select');
    select.innerHTML = '<option value="">(No specific task context)</option>' +
        state.tasks.map(t => `<option value="${t.id}">${t.type === 'recurring' ? '🔥' : '📋'} ${t.title}</option>`).join('');
}

// Handle AI Chat submissions
document.getElementById('copilot-send-btn').addEventListener('click', sendCopilotMessage);
document.getElementById('copilot-user-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendCopilotMessage();
});

// Prompt recommendation clicker
document.querySelectorAll('.rec-chip').forEach(chip => {
    chip.addEventListener('click', () => {
        const text = chip.getAttribute('data-prompt');
        document.getElementById('copilot-user-input').value = text;
        sendCopilotMessage();
    });
});

async function sendCopilotMessage() {
    const input = document.getElementById('copilot-user-input');
    const taskSelect = document.getElementById('copilot-task-select');
    const prompt = input.value.trim();
    
    if (!prompt) return;

    const taskId = taskSelect.value;

    // Append user message
    appendMessage(prompt, 'user-message');
    input.value = '';

    // Append loading bubble
    const loadingId = appendMessage('Consulting AI Co-pilot...', 'ai-message loading');

    try {
        const res = await apiFetch(`${API_BASE}/tasks/ai-copilot/`, {
            method: 'POST',
            body: { task_id: taskId ? parseInt(taskId) : null, prompt }
        });
        
        // Remove loading
        document.getElementById(loadingId).remove();

        if (res.ok) {
            const data = await res.json();
            appendMessage(data.response, 'ai-message');
        } else {
            appendMessage('Failed to consult AI Copilot service. Check network parameters.', 'ai-message');
        }
    } catch (e) {
        document.getElementById(loadingId).remove();
        appendMessage('API Error: AI helper connection dropped.', 'ai-message');
    }
}

function appendMessage(text, className) {
    const container = document.getElementById('copilot-messages-container');
    const bubble = document.createElement('div');
    bubble.className = `message ${className}`;
    const uniqueId = 'msg-' + Math.random().toString(36).substr(2, 9);
    bubble.id = uniqueId;
    bubble.innerHTML = text.replace(/\n/g, '<br>');
    container.appendChild(bubble);
    
    // Auto-scroll
    container.scrollTop = container.scrollHeight;
    return uniqueId;
}

// ==============================================================================
// 11. Modal actions (Task & Project creations)
// ==============================================================================
const taskModal = document.getElementById('create-task-modal');
const projectModal = document.getElementById('create-project-modal');

document.getElementById('quick-create-task-btn').addEventListener('click', () => {
    document.getElementById('task-modal-title').textContent = 'Create New Task';
    document.getElementById('edit-task-id').value = '';
    document.getElementById('task-create-form').reset();
    populateTaskModalDropdowns();
    taskModal.classList.add('active');
});

document.getElementById('close-task-modal-btn').addEventListener('click', () => {
    taskModal.classList.remove('active');
});

document.getElementById('create-project-btn').addEventListener('click', () => {
    document.getElementById('project-create-form').reset();
    projectModal.classList.add('active');
});

document.getElementById('close-project-modal-btn').addEventListener('click', () => {
    projectModal.classList.remove('active');
});

function populateTaskModalDropdowns() {
    const projSelect = document.getElementById('task-project');
    projSelect.innerHTML = state.projects.map(p => `<option value="${p.id}">${p.title}</option>`).join('');
    
    const depSelect = document.getElementById('task-dependency');
    depSelect.innerHTML = '<option value="">None (Not Blocked)</option>' + 
        state.tasks.filter(t => t.type === 'one_off' && t.status !== 'done')
                   .map(t => `<option value="${t.id}">${t.title}</option>`).join('');
}

function openNewTaskModalWithProject(projectId) {
    document.getElementById('task-modal-title').textContent = 'Create New Task';
    document.getElementById('edit-task-id').value = '';
    document.getElementById('task-create-form').reset();
    populateTaskModalDropdowns();
    document.getElementById('task-project').value = projectId;
    taskModal.classList.add('active');
}

// Handle Task submission
document.getElementById('task-create-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const taskId = document.getElementById('edit-task-id').value;
    const title = document.getElementById('task-title').value;
    const description = document.getElementById('task-description').value;
    const project = parseInt(document.getElementById('task-project').value);
    const type = document.getElementById('task-type').value;
    const priority = document.getElementById('task-priority').value;
    const depends_on_task = document.getElementById('task-dependency').value ? parseInt(document.getElementById('task-dependency').value) : null;
    
    let due_date = document.getElementById('task-due-date').value;
    if (due_date) {
        due_date = new Date(due_date).toISOString();
    } else {
        due_date = null;
    }

    const payload = { title, description, project, type, priority, depends_on_task, due_date };

    let res;
    if (taskId) {
        // Edit mode
        res = await apiFetch(`${API_BASE}/tasks/${taskId}/`, {
            method: 'PUT',
            body: payload
        });
    } else {
        // Create mode
        res = await apiFetch(`${API_BASE}/tasks/`, {
            method: 'POST',
            body: payload
        });
    }

    if (res.ok) {
        showToast(taskId ? 'Task updated!' : 'Task created!', 'success');
        taskModal.classList.remove('active');
        
        // Reload current tab content
        await loadTasks();
        await loadTabData(state.currentTab);
    } else {
        const err = await res.json();
        let msg = 'Failed to save task.';
        if (err.due_date) msg = err.due_date[0];
        else if (err.status) msg = err.status[0];
        else if (err.depends_on_task) msg = err.depends_on_task[0];
        showToast(msg, 'danger');
    }
});

// Edit task handler
async function editTask(id) {
    const t = state.tasks.find(task => task.id === id);
    if (!t) return;
    
    document.getElementById('task-modal-title').textContent = 'Edit Task';
    document.getElementById('edit-task-id').value = t.id;
    document.getElementById('task-title').value = t.title;
    document.getElementById('task-description').value = t.description || '';
    
    populateTaskModalDropdowns();
    document.getElementById('task-project').value = t.project;
    document.getElementById('task-type').value = t.type;
    document.getElementById('task-priority').value = t.priority;
    
    if (t.due_date) {
        const localDate = new Date(t.due_date);
        localDate.setMinutes(localDate.getMinutes() - localDate.getTimezoneOffset());
        document.getElementById('task-due-date').value = localDate.toISOString().slice(0, 16);
    } else {
        document.getElementById('task-due-date').value = '';
    }
    
    document.getElementById('task-dependency').value = t.depends_on_task || '';
    taskModal.classList.add('active');
}

// Handle Project creation
document.getElementById('project-create-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const title = document.getElementById('project-title').value;
    const description = document.getElementById('project-description').value;

    const res = await apiFetch(`${API_BASE}/projects/`, {
        method: 'POST',
        body: { title, description }
    });

    if (res.ok) {
        showToast('Project created successfully!', 'success');
        projectModal.classList.remove('active');
        await loadProjects();
        await loadTabData(state.currentTab);
    } else {
        showToast('Failed to create project.', 'danger');
    }
});

// Create Habit button (navigates or triggers modal)
const createHabitBtn = document.getElementById('create-habit-btn');
if (createHabitBtn) {
    createHabitBtn.addEventListener('click', () => {
        document.getElementById('task-modal-title').textContent = 'Add Habit';
        document.getElementById('edit-task-id').value = '';
        document.getElementById('task-create-form').reset();
        populateTaskModalDropdowns();
        document.getElementById('task-type').value = 'recurring';
        taskModal.classList.add('active');
    });
}

// ==============================================================================
// 12. Settings Form Submission
// ==============================================================================
document.getElementById('profile-settings-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const timezone = document.getElementById('profile-timezone').value;
    const reset_hour = parseInt(document.getElementById('profile-reset-hour').value);

    const res = await apiFetch(`${API_BASE}/auth/profile/`, {
        method: 'PATCH',
        body: { timezone, reset_hour }
    });

    if (res.ok) {
        showToast('Profile settings updated!', 'success');
        await loadUserData();
    } else {
        showToast('Failed to update settings.', 'danger');
    }
});

// ==============================================================================
// 13. Application Initialization
// ==============================================================================
async function initApp() {
    if (state.accessToken) {
        try {
            hideAuthOverlay();
            await loadTabData(state.currentTab);
        } catch (e) {
            logout();
        }
    } else {
        showAuthOverlay();
    }
}

// Run init
window.addEventListener('DOMContentLoaded', initApp);
