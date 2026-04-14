/**
 * Admin Authentication Script
 * Protects admin pages with a password challenge.
 */

(function () {
    // Configuration
    const AUTH_ENDPOINT = '/api/admin/verify';
    const SESSION_KEY = 'admin_access_token';
    const VALID_TOKEN = 'admin_access_granted_v1';

    // Check if already authenticated
    function isAuthenticated() {
        const token = sessionStorage.getItem(SESSION_KEY);
        console.log('Admin Auth: Checking session...', token ? 'Token exists' : 'No token');
        return token === VALID_TOKEN;
    }

    // Initialize Auth
    function init() {
        console.log('Admin Auth: Initializing script...');
        if (isAuthenticated()) {
            console.log('Admin Auth: Already authenticated.');
            addLogoutButton();
            return;
        }

        if (document.getElementById('admin-login-overlay')) {
            console.log('Admin Auth: Overlay already exists, skipping creation.');
            return;
        }

        // Lock the page content
        document.documentElement.style.overflow = 'hidden';
        showLoginOverlay();
    }

    function showLoginOverlay() {
        const overlay = document.createElement('div');
        overlay.id = 'admin-login-overlay';
        overlay.innerHTML = `
            <style>
                #admin-login-overlay {
                    position: fixed;
                    inset: 0;
                    z-index: 10000;
                    background: #060b18;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-family: 'Inter', sans-serif;
                    padding: 20px;
                    pointer-events: all !important;
                }
                #admin-login-overlay::before {
                    content: '';
                    position: absolute;
                    inset: 0;
                    background-image: 
                        radial-gradient(circle at 20% 20%, rgba(34, 197, 94, 0.1) 0%, transparent 40%),
                        radial-gradient(circle at 80% 80%, rgba(59, 130, 246, 0.1) 0%, transparent 40%);
                    z-index: -1;
                }
                .admin-auth-card {
                    background: rgba(15, 23, 42, 0.7);
                    backdrop-filter: blur(24px) saturate(1.5);
                    -webkit-backdrop-filter: blur(24px) saturate(1.5);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 2rem;
                    padding: 3rem;
                    width: 100%;
                    max-width: 420px;
                    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
                    animation: cardAppear 0.6s cubic-bezier(0.16, 1, 0.3, 1);
                    text-align: center;
                    pointer-events: auto !important;
                }
                @keyframes cardAppear {
                    from { opacity: 0; transform: translateY(20px) scale(0.95); }
                    to { opacity: 1; transform: translateY(0) scale(1); }
                }
                .login-icon {
                    width: 64px;
                    height: 64px;
                    background: linear-gradient(135deg, rgba(34, 197, 94, 0.2), rgba(34, 197, 94, 0.05));
                    border: 1px solid rgba(34, 197, 94, 0.3);
                    border-radius: 1.25rem;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin: 0 auto 1.5rem;
                    color: #22c55e;
                    font-size: 1.5rem;
                    box-shadow: 0 0 20px rgba(34, 197, 94, 0.1);
                    pointer-events: none;
                }
                .login-title {
                    font-size: 1.5rem;
                    font-weight: 900;
                    color: #fff;
                    text-transform: uppercase;
                    letter-spacing: -0.02em;
                    margin-bottom: 0.5rem;
                    font-style: italic;
                }
                .login-subtitle {
                    font-size: 0.75rem;
                    font-weight: 700;
                    color: #64748b;
                    text-transform: uppercase;
                    letter-spacing: 0.2em;
                    margin-bottom: 2.5rem;
                    display: block;
                }
                .input-group {
                    position: relative;
                    margin-bottom: 1.5rem;
                }
                .login-input {
                    background: rgba(6, 11, 24, 0.8);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 1rem;
                    width: 100%;
                    padding: 1rem 1.25rem;
                    color: #fff;
                    font-size: 1rem;
                    outline: none;
                    transition: all 0.3s;
                    text-align: center;
                    letter-spacing: 0.5em;
                }
                .login-input:focus {
                    border-color: #22c55e;
                    box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.15);
                    background: #060b18;
                }
                .admin-auth-btn {
                    background: #22c55e;
                    color: #060b18;
                    width: 100%;
                    padding: 1rem;
                    border: none;
                    border-radius: 1rem;
                    font-weight: 800;
                    font-size: 0.875rem;
                    text-transform: uppercase;
                    letter-spacing: 0.1em;
                    cursor: pointer;
                    transition: all 0.3s;
                    margin-top: 1rem;
                    box-shadow: 0 10px 15px -3px rgba(34, 197, 94, 0.2);
                    pointer-events: auto !important;
                }
                .admin-auth-btn:hover {
                    background: #26d666;
                    transform: translateY(-2px);
                    box-shadow: 0 20px 25px -5px rgba(34, 197, 94, 0.25);
                }
                .admin-auth-btn:active {
                    transform: translateY(0);
                }
                .admin-auth-btn:disabled {
                    opacity: 0.6;
                    cursor: not-allowed;
                    transform: none;
                }
                .error-msg {
                    color: #ef4444;
                    font-size: 0.75rem;
                    font-weight: 600;
                    margin-top: 1rem;
                    opacity: 0;
                    transition: opacity 0.3s;
                }
                .error-msg.visible { opacity: 1; }
                
                @keyframes pulse-ring {
                    0% { transform: scale(0.8); opacity: 0.5; }
                    100% { transform: scale(1.2); opacity: 0; }
                }
                .pulse {
                    position: absolute;
                    inset: -4px;
                    border: 2px solid #22c55e;
                    border-radius: 1.25rem;
                    animation: pulse-ring 2s cubic-bezier(0.25, 0.46, 0.45, 0.94) infinite;
                    pointer-events: none;
                }
            </style>
            <div class="admin-auth-card">
                <div class="login-icon">
                    <div class="pulse"></div>
                    <i class="fas fa-lock text-green-500"></i>
                </div>
                <h2 class="login-title">Панель адміністратора</h2>
                <span class="login-subtitle">Доступ обмежено</span>
                
                <form id="admin-login-form">
                    <div class="input-group">
                        <input type="password" id="admin-password" class="login-input" placeholder="••••••" autofocus required>
                    </div>
                    <button type="submit" class="admin-auth-btn" id="admin-login-submit">
                        Перевірити авторизацію
                    </button>
                    <div id="admin-error-msg" class="error-msg">Доступ заборонено: невірний пароль</div>
                </form>

                <div style="margin-top: 2rem;">
                    <button onclick="window.location.href='/'" style="background:none; border:none; color:#64748b; font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.1em; cursor:pointer; text-decoration:underline;">
                        Повернутися до терміналу
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);
        console.log('Admin Auth: Overlay appended to body.');

        const form = overlay.querySelector('#admin-login-form');
        const submitBtn = overlay.querySelector('#admin-login-submit');
        const errorMsg = overlay.querySelector('#admin-error-msg');
        const passwordInput = overlay.querySelector('#admin-password');

        let isSubmitting = false;

        if (!form || !submitBtn) {
            console.error('Admin Auth: Failed to find form elements in overlay!');
            return;
        }

        const handleFormSubmit = async (e) => {
            if (e) e.preventDefault();
            if (isSubmitting) return;

            console.log('Admin Auth: Form submission triggered.');

            const password = passwordInput.value;
            if (!password) {
                console.warn('Admin Auth: Password field is empty.');
                if (form.reportValidity) form.reportValidity();
                return;
            }

            isSubmitting = true;
            errorMsg.classList.remove('visible');
            submitBtn.disabled = true;
            submitBtn.innerText = 'Перевірка...';
            console.log('Admin Auth: Sending request to', AUTH_ENDPOINT);

            try {
                const response = await fetch(AUTH_ENDPOINT, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ password })
                });

                console.log('Admin Auth: Server response status:', response.status);

                if (response.ok) {
                    const data = await response.json();
                    sessionStorage.setItem(SESSION_KEY, data.token);
                    console.log('Admin Auth: Login successful, storing token.');

                    // Success! Remove overlay and unlock scroll
                    overlay.style.transition = 'opacity 0.6s cubic-bezier(0.16, 1, 0.3, 1)';
                    overlay.style.opacity = '0';
                    setTimeout(() => {
                        overlay.remove();
                        document.documentElement.style.overflow = '';
                        location.reload();
                    }, 600);
                } else {
                    console.warn('Admin Auth: Authentication failed (Invalid password).');
                    errorMsg.classList.add('visible');
                    passwordInput.value = '';
                    passwordInput.focus();
                }
            } catch (err) {
                console.error('Admin Auth: Network/Connection error:', err);
                alert('Помилка з\'єднання. Будь ласка, спробуйте ще раз.');
            } finally {
                isSubmitting = false;
                submitBtn.disabled = false;
                submitBtn.innerText = 'Перевірити авторизацію';
            }
        };

        form.addEventListener('submit', handleFormSubmit);
        console.log('Admin Auth: Submit listener attached to form.');

        // Debug: Track any click on overlay
        overlay.addEventListener('click', (e) => {
            console.log('Admin Auth: Click on overlay. Target:', e.target.tagName, 'ID:', e.target.id, 'Class:', e.target.className);
        });

        // Fallback for click if submit event is blocked
        submitBtn.addEventListener('click', (e) => {
            console.log('Admin Auth: Submit button clicked.');
            if (form.reportValidity && !form.checkValidity()) {
                console.warn('Admin Auth: Form validation failed.');
                return;
            }
            if (!isSubmitting) {
                handleFormSubmit(e);
            }
        });
        console.log('Admin Auth: Click listener attached to button.');
    }

    function addLogoutButton() {
        const btn = document.createElement('button');
        btn.id = 'admin-logout-btn';
        btn.innerHTML = '<i class="fas fa-power-off"></i>';
        btn.title = 'Logout Admin Session';
        btn.style.cssText = `
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            z-index: 9999;
            width: 50px;
            height: 50px;
            border-radius: 1rem;
            background: rgba(239, 68, 68, 0.1);
            color: #ef4444;
            border: 1px solid rgba(239, 68, 68, 0.2);
            cursor: pointer;
            backdrop-filter: blur(10px);
            transition: all 0.3s;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
        `;
        btn.onmouseover = () => {
            btn.style.background = '#ef4444';
            btn.style.color = '#fff';
            btn.style.transform = 'translateY(-2px)';
        };
        btn.onmouseout = () => {
            btn.style.background = 'rgba(239, 68, 68, 0.1)';
            btn.style.color = '#ef4444';
            btn.style.transform = 'translateY(0)';
        };
        btn.onclick = () => {
            sessionStorage.removeItem(SESSION_KEY);
            location.reload();
        };
        document.body.appendChild(btn);
    }

    // Start
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
