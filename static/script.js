const API_URL = "" // Пустая строка, так как фронт и бэк на одном домене

// --- 1. Функция Входа (Login) ---
async function login() {
    const usernameInput = document.getElementById('username').value
    const passwordInput = document.getElementById('password').value
    const responseArea = document.getElementById('response-area')

    // Важный момент! FastAPI (OAuth2) ждет данные в формате application/x-www-form-urlencoded
    // Это НЕ обычный JSON. Поэтому используем FormData.
    const formData = new FormData()
    formData.append('username', usernameInput)
    formData.append('password', passwordInput)

    try {
        const response = await fetch(`${API_URL}/auth/login`, {
            method: 'POST',
            body: formData, // Браузер сам выставит правильные заголовки для FormData

        })

        const data = await response.json()

        // Выводим ответ на экран
        responseArea.innerText = JSON.stringify(data, null, 2)

        if (response.ok) {
            // Если успех - сохраняем токен в память браузера
            localStorage.setItem('accessToken', data.access_token)
            showDashboard(data.access_token)
        } else {
            alert('Ошибка входа: ' + data.detail)
        }
    } catch (error) {
        responseArea.innerText = "Ошибка сети: " + error
    }
}


// --- 2. Функция получения данных о себе (Защищенный роут) ---
async function getMe() {
    const token = localStorage.getItem('accessToken')
    const responseArea = document.getElementById('response-area')

    try { 
        const response = await fetch(`${API_URL}/auth/me`, {
            method: 'GET',
            headers: {
                // Самое главное в JWT. Передаем токен в заголовке.
                'Authorization': `Bearer ${token}`
            }
        })

        const data = await response.json()
        responseArea.innerText = JSON.stringify(data, null, 2)
    } catch (error) {
        responseArea.innerText = "Ошибка: " + error
    }
}


// --- 3. Функция получения товаров ---
async function getProducts() {
    const responseArea = document.getElementById('response-area')
    try {
        const response = await fetch(`${API_URL}/products/`)
        const data = await response.json()
        responseArea.innerText =  JSON.stringify(data, null, 2)
    } catch (error) {
        responseArea.innerText = "Ошибка: " + error
    }
}

// --- Утилиты для интерфейса ---
function showDashboard(token) {
    document.getElementById('login-section').classList.add('hidden')
    document.getElementById('dashboard-section').classList.remove('hidden')
    document.getElementById('token-display').innerText = token.substring(0, 20) + "..."
}

function logout() {
    localStorage.removeItem('accessToken')
    location.reload() // Перезагружаем страницу
}

// При загрузке страницы проверяем, есть ли уже токен
window.onload = function() {
    const token = localStorage.getItem('accessToken')
    if (token) {
        showDashboard(token)
    }
}






















