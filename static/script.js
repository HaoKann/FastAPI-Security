const API_URL = "" // Пустая строка, так как фронт и бэк на одном домене


// --- Функция переключения между Входом и Регистрацией ---
function toggleAuth(mode) {
    if (mode === 'register') {
        document.getElementById('login-box').classList.add('hidden')
        document.getElementById('register-box').classList.remove('hidden')
    } else {
        document.getElementById('register-box').classList.add('hidden')
        document.getElementById('login-box').classList.remove('hidden')
    }
}

// --- Функция Регистрации ---
async function register() {
    const usernameInput = document.getElementById('reg-username').value
    const passwordInput = document.getElementById('reg-password').value
    const responseArea = document.getElementById('response-area')

    // ВАЖНО: В отличие от логина, здесь мы отправляем обычный JSON!
    const payload = {
        username: usernameInput,
        password: passwordInput
    }

    try {
        const response = await fetch(`${API_URL}/auth/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json' // Говорим серверу, что шлем JSON
            },
            body: JSON.stringify(payload)
        })

        const data = await response.json()
        responseArea.innerText = JSON.stringify(data, null, 2)

        if (response.ok) {
            // Твой бэкенд сразу выдает токены при регистрации! 
            // Значит, нам не нужно просить юзера логиниться заново. Мы сразу пускаем его внутрь!
            alert('Аккаунт успешно создан! Вы вошли в систему.');
            localStorage.setItem('accessToken', data.access_token)
            showDashboard(data.access_token)
        } else {
            alert('Ошибка регистрации: ' + data.detail)
        }
    } catch (error) {
        responseArea.innerText = 'Ошибка сети: ' + error
    }

}

//  Функция Входа (Login) ---
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

        // Если сервер упал (например, 500 ошибка), ловим текст ошибки, чтобы не было "Unexpected token I"
        if (!response.ok) {
            const errorText = await response.text()
            responseArea.innerText = `Ошибка сервера (${response.status}): ${errorText}`
            return
        }
        
        const products = await response.json()

       // РИСУЕМ КРАСИВЫЕ КАРТОЧКИ! 🎨
        let html = `
            <h3 style="margin-bottom: 15px; color: #667eea;">📦 Витрина товаров</h3>
            <div style="display: flex; flex-wrap: wrap; gap: 15px;">
        `;
        
        if (products.length === 0) {
            html += `<p style="color: #718096; width: 100%;">У вас пока нет ни одного товара.</p>`;
        } else {
            products.forEach(p => {
                html += `
                <div style="background: white; border: 2px solid #edf2f7; border-radius: 12px; padding: 20px; width: 220px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); transition: transform 0.2s;">
                    <h4 style="margin-bottom: 10px; color: #2d3748; font-size: 1.2em;">${p.name}</h4>
                    <p style="color: #48bb78; font-weight: 800; font-size: 1.4em; margin-bottom: 10px;">$${p.price}</p>
                    <span style="background: #edf2f7; color: #4a5568; padding: 4px 8px; border-radius: 6px; font-size: 0.8em;">ID: ${p.id.substring(0,6)}...</span>
                </div>
                `;
            });
        }
        html += `</div>`;
        
        // Вставляем карточки прямо в наш блок ответа
        responseArea.innerHTML = html;
        
    } catch (error) {
        responseArea.innerText = "Ошибка: " + error
    }
}

// --- 5. Функция создания нового товара ---
async function createProduct() {
    const token = localStorage.getItem('accessToken')
    const nameInput = document.getElementById('new-product-name')
    const priceInput = document.getElementById('new-product-price')
    const responseArea = document.getElementById('response-area')


    
    // Проверяем, что поля не пустые
    if (!nameInput.value || !priceInput.value) {
        alert("Пожалуйста, введите название и цену товара!")
        return
    }

    // Собираем данные в JSON (в таком виде их ждет Pydantic модель на бэкенде)
    const payload = {
        name: nameInput.value,
        price: parseFloat(priceInput.value)
    }

    try {
        // Делаем POST-запрос на создание товара
        const response = await fetch(`${API_URL}/products/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(payload)
        })

        if (response.ok) {
            // Очищаем поля ввода после успешного создания
            nameInput.value = ''
            priceInput.value = ''

            // МАГИЯ: Сразу запрашиваем обновленный список товаров, 
            // чтобы новая карточка мгновенно появилась на экране!
            getProducts()
        } else {
            const errorData = await response.json()
            alert('Ошибка создания товара: '+ (errorData.detail || 'Неизвестная ошибка'))
        } 

    } catch (error){
        responseArea.innerText = "Ошибка сети: " + error
    }
}


// --- Утилиты для интерфейса ---
function showDashboard(token) {
    document.getElementById('auth-section').classList.add('hidden')
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
