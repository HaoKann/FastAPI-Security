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
        
        //  НОВАЯ ЛОГИКА: Обновляем интерфейс, если запрос успешен
        if (response.ok) {
            document.getElementById('display-username').innerText = data.username
            
            // Если у юзера есть аватарка в базе, ставим её. Если нет - останется заглушка.
            if (data.avatar_url) {
                document.getElementById('avatar-image').src = data.avatar_url
            }
        }
    } catch (error) {
        responseArea.innerText = "Ошибка: " + error
    }
}

// --- 3. НОВАЯ ФУНКЦИЯ: Загрузка аватарки ---
async function uploadAvatar() {
    const token = localStorage.getItem('accessToken')
    const fileInput = document.getElementById('avatar-input')
    const responseArea = document.getElementById('response-area')

    // Проверяем, выбрал ли пользователь файл
    if (fileInput.files.length === 0) {
        alert('Пожалуйста, выберите картинку!')
        return
    }

    const file = fileInput.files[0]
    const formData = new FormData()
    // Имя поля 'file' должно ТОЧНО совпадать с названием параметра в FastAPI: def update_avatar(file: UploadFile = File(...))
    formData.append('file', file);

    try {
        const response = await fetch(`${API_URL}/users/me/avatar`, {
            method: 'PATCH',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        })

        const data = await response.json()
        responseArea.innerText = JSON.stringify(data, null, 2)

        if (response.ok) {
            // Вместо ручной вставки короткой ссылки, просто вызываем getMe()
            // Он сам сходит на бэкенд, получит временный URL на 1 час и отрисует картинку!
            getMe()
        } else {
            alert('Ошибка загрузки: ' + data.detail)
        }
    } catch (error) {
        responseArea.innerText = "Ошибка сети: " + error
    }

}

// --- 4. Функция получения товаров с токеном---
async function getProducts() {
    const token = localStorage.getItem('accessToken') // <-- 1. Достаем токен
    const responseArea = document.getElementById('response-area')

    try {
        const response = await fetch(`${API_URL}/products/`, {  // <-- 2. Добавляем настройки запроса
            method: 'GET',
            headers: {
                // <-- 3. Предъявляем пропуск (токен)
                'Authorization': `Bearer ${token}`
            }
        }) 
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

    // Автоматически запрашиваем профиль, чтобы сразу показать аватарку
    getMe()
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
