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
                let finalAvatarUrl = data.avatar_url

                // Если бэкенд отдал просто имя файла (например, "123.png"),
                // мы сами собираем ссылку на MinIO:
                if (!finalAvatarUrl.startsWith('http')) {
                    finalAvatarUrl = `http://localhost:9000/test-bucket/${finalAvatarUrl}`
                }

                // Меняем докеровский адрес на локальный, чтобы браузер понял, откуда качать
                else if (finalAvatarUrl.includes('minio:9000')) {
                    finalAvatarUrl = finalAvatarUrl.replace('minio:9000', 'localhost:9000')
                }

                document.getElementById('avatar-image').src = finalAvatarUrl
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
            method: 'POST',
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
            // ЛОВИМ ПОДРОБНУЮ ОШИБКУ ОТ FASTAPI
            const errorData = await response.json()
            const errorDetail = JSON.stringify(errorData.detail, null, 2)
            alert('FastAPI жалуется на данные:\n' + errorDetail)
        }
    } catch (error) {
        // ВОТ ЗДЕСЬ БЫЛ ОБРЫВ. ТЕПЕРЬ ВСЁ ИСПРАВЛЕНО:
        responseArea.innerText = "Ошибка сети: " + error
    } 
} // <---

// --- ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ДЛЯ ПАГИНАЦИИ ---
let currentOffset = 0
const LIMIT = 2 // Выводим по 2 товара на страницу для наглядности


// --- 4. Функция получения товаров с токеном ---
async function getProducts() {
    const token = localStorage.getItem('accessToken')
    const responseArea = document.getElementById('response-area')
    const productsArea = document.getElementById('products-area')

    try {
        const response = await fetch(`${API_URL}/products/all?limit=${LIMIT}&offset=${currentOffset}`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        })

        if (!response.ok) {
            const errorText = await response.text()
            responseArea.innerText = `Ошибка сервера (${response.status}): ${errorText}`
            return
        }
        
        const products = await response.json()
        const currentUsername = document.getElementById('display-username').innerText

        // 🎨 Обновленная витрина: Используем классы темной темы из index.html
        let html = `
            <h3 style="margin-bottom: 20px; color: var(--text-main); display: flex; align-items: center; gap: 8px;">
                <span>📦</span> Витрина товаров
            </h3>
            <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 20px; margin-bottom: 20px;">
        `;
        
        if (products.length === 0 && currentOffset === 0) {
            html += `<p style="color: var(--secondary-text); grid-column: 1 / -1;">У вас пока нет ни одного товара.</p>`;
        } else if (products.length === 0) {
            html += `<p style="color: var(--secondary-text); grid-column: 1 / -1;">Больше товаров нет.</p>`;
        } else {
            products.forEach(p => {
                let buttonsHtml = '' 
                
                // Стили для аккуратных кнопок с использованием переменных темной темы
                const btnPrimary = `background: var(--primary); color: white; padding: 10px; border-radius: 8px; border: none; cursor: pointer; font-weight: 600; width: 100%; transition: all 0.2s;`
                const btnAction = `background: var(--secondary); color: var(--text-main); padding: 8px; border-radius: 8px; border: none; cursor: pointer; font-weight: 600; flex: 1; transition: all 0.2s;`

                if (p.owner_username === currentUsername) {
                    buttonsHtml = `
                        <div style="margin-top: auto; display: flex; gap: 8px;">
                            <button onclick="editProduct('${p.id}', '${p.name}', ${p.price})" style="${btnAction}">✏️ Цена</button>
                            <button onclick="deleteProduct('${p.id}')" style="${btnAction}">🗑️ Удал.</button>
                        </div>
                    `;
                } else {
                    buttonsHtml = `
                        <div style="margin-top: auto;">
                            <button onclick="buyProduct('${p.id}')" style="${btnPrimary}">💳 Купить</button>
                        </div>
                    `;
                }
                
                // ВМЕСТО ИНЛАЙН СТИЛЕЙ ИСПОЛЬЗУЕМ КЛАСС .glass-card 
                html += `
                <div class="glass-card" style="display: flex; flex-direction: column; min-height: 200px;">
                    <h4 style="margin-bottom: 8px; color: var(--text-main); font-size: 1.1em; line-height: 1.3;">${p.name}</h4>
                    <p style="color: var(--primary); font-weight: 800; font-size: 1.4em; margin-bottom: 4px;">$${p.price}</p>
                    
                    <p style="color: #fbbf24; font-size: 0.85em; margin-bottom: 12px; font-weight: 600;">
                        С налогом: $${p.price_with_tax}
                    </p>

                    <div style="margin-bottom: 16px;">
                        <span style="background: var(--bg-main); color: var(--secondary-text); padding: 4px 8px; border-radius: 6px; font-size: 0.75em; border: 1px solid var(--border);">
                            ID: ${p.id}
                        </span>
                    </div>
                    
                    ${buttonsHtml}
                </div>
                `;
            });
        }
        html += `</div>`;

        // Кнопки пагинации
        const currentPage = (currentOffset / LIMIT) + 1
        const isLastPage = products.length < LIMIT 
        
        const pagBtnStyle = `padding: 10px 20px; border-radius: 8px; border: none; font-weight: 600; transition: 0.2s;`
        
        html += `
        <div style="display: flex; gap: 15px; align-items: center; justify-content: center; width: 100%;">
            <button onclick="prevPage()" ${currentOffset === 0 ? 'disabled' : ''} 
                    style="${pagBtnStyle} background: ${currentOffset === 0 ? 'var(--bg-main)' : 'var(--primary)'}; color: ${currentOffset === 0 ? 'var(--secondary-text)' : 'white'}; cursor: ${currentOffset === 0 ? 'not-allowed' : 'pointer'};">
                ⬅️ Назад
            </button>

            <span style="color: var(--text-main); font-weight: 600; font-size: 0.95em;">
                Стр. ${currentPage}
            </span>

            <button onclick="nextPage(${isLastPage})" ${isLastPage ? 'disabled' : ''} 
                    style="${pagBtnStyle} background: ${isLastPage ? 'var(--bg-main)' : 'var(--primary)'}; color: ${isLastPage ? 'var(--secondary-text)' : 'white'}; cursor: ${isLastPage ? 'not-allowed' : 'pointer'};">
                Вперед ➡️
            </button>
        </div>
        `;

        productsArea.innerHTML = html;
        responseArea.innerText = JSON.stringify(products, null, 2)

    } catch (error) {
        responseArea.innerText = "Ошибка: " + error
    }
}

// --- ФУНКЦИИ УПРАВЛЕНИЯ ПАГИНАЦИЕЙ ---

function prevPage() {
    if (currentOffset >= LIMIT) {
        currentOffset -= LIMIT; // Уменьшаем отступ
        getProducts(); // Заново запрашиваем товары
    }
}

function nextPage(isLastPage) {
    if (!isLastPage) {
        currentOffset += LIMIT; // Увеличиваем отступ
        getProducts(); // Заново запрашиваем товары
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
            // ПРОКАЧАННАЯ ОБРАБОТКА ОШИБОК
            // Если detail — это массив (как у Pydantic), превращаем его в читаемый текст
            const errorMessage = typeof errorData.detail === 'object'
                ? JSON.stringify(errorData.detail)
                : errorData.detail

            alert('Ошибка: '+ errorMessage)
        } 

    } catch (error){
        responseArea.innerText = "Ошибка сети: " + error
    }
}


// --- Функция обновления цены товара ---
async function editProduct(productID, currentName, currentPrice) {
    const newPriceStr = prompt(`Введите новую цену для товара "${currentName}":`, currentPrice)

    if (newPriceStr === null) return // Юзер нажал "Отмена"

    const newPrice = parseFloat(newPriceStr)
    if (isNaN(newPrice) || newPrice <= 0) {
        alert("Пожалуйста, введите корректную цену (число больше 0)!");
        return
    }

    const token = localStorage.getItem('accessToken')
    try {
        const response = await fetch(`${API_URL}/products/${productID}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ price: newPrice })
        })

        if (response.ok) {
            getProducts()
        } else {
            const data = await response.json()
            alert("Ошибка при обновлении: " + (data.detail || "Неизвестная ошибка"));
        }
    } catch (error) {
        alert("Ошибка сети: " + error)
    }
}

// --- Функция удаления товара ---
async function deleteProduct(productId) {
    if (!confirm("Вы уверены, что хотите удалить этот товар?")) return;

    const token = localStorage.getItem('accessToken');
    try {
        const response = await fetch(`${API_URL}/products/${productId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (response.ok) {
            getProducts(); // Мгновенно перерисовываем витрину!
        } else {
            const data = await response.json();
            alert("Ошибка при удалении: " + (data.detail || "Неизвестная ошибка"));
        }
    } catch (error) {
        alert("Ошибка сети: " + error);
    }
}


// --- Утилиты для интерфейса ---
function showDashboard(token) {
    document.getElementById('auth-section').classList.add('hidden')
    document.getElementById('dashboard-section').classList.remove('hidden')

    // Автоматически запрашиваем профиль, чтобы сразу показать аватарку
    getMe()

    // НОВОЕ: Автоматически подключаем WebSockets
    connectWebSocket(token)
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


// ==========================================
// 🚀 WEBSOCKETS И ФОНОВЫЕ ЗАДАЧИ (CELERY)
// ==========================================

let ws = null


// Функция для добавления логов в черное окошко
function addNotification(message) {
    const notifArea = document.getElementById('notifications-area')
    const time = new Date().toLocaleTimeString()
    notifArea.innerHTML += `<div style="margin-bottom: 5px;">[${time}] ${message}</div>`
    notifArea.scrollTop = notifArea.scrollHeight
}


// Подключаемся к вебсокету
function connectWebSocket(token) {
    // Закрываем старое соединение, если оно вдруг есть
    if (ws) {
            ws.close()
        }
    

    // для WebSockets используется протокол ws:// вместо http://
    // Так как бэкенд и фронт на одном хосте, берем адрес из window.location.host
    const wsUrl = `ws://${window.location.host}/ws/notifications?token=${token}`

    ws = new WebSocket(wsUrl)

    const indicator = document.getElementById('ws-indicator')
    const statusText = document.getElementById('ws-status-text')

    ws.onopen = function() {
        indicator.style.background = '#48bb78'
        statusText.innerText = 'WebSockets: Подключено'
        statusText.style.color = '#48bb78'
        addNotification('🟢 Соединение с сервером установлено. Ждем уведомлений...')
    }

    ws.onmessage = function(event) {
        // Когда сервер присылает сообщение, выводим его
        addNotification(`🔔 ${event.data}`)
    }

    ws.onclose = function() {
        indicator.style.background = 'rgb(251,8,8)'
        statusText.innerText = 'WebSocket: Отключено'
        statusText.style.color =  'rgb(251,8,8)'
        addNotification('🔴 Соединение разорвано.')
    }

    ws.onerror = function(error) {
        addNotification('❌ Ошибка WebSocket.')
    }
}

// Отправляем задачу в Celery
async function startFactorialTask() {
    const token = localStorage.getItem('accessToken')
    const inputElement = document.getElementById('factorial-input')
    const number = parseInt(inputElement.value)

    if (!number || number <= 0) {
        alert('Пожалуйста, введите положительное число.')
        return
    }

    addNotification(`⏳ Отправляем задачу: факториал числа ${number}...`)

    try {
        const response = await fetch(`${API_URL}/compute/factorial`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ n: number })
        })

        if (response.status == 202) {
            addNotification('✅ Задача принята сервером. Воркер Celery начал вычисления.')
            inputElement.value = ''
        } else {
            const data = await response.json()
            addNotification(`❌ Ошибка отправки: ${data.detail || response.status}`)
        }
    } catch (error) {
            addNotification(`❌ Ошибка сети: ${error}`)
        }
    }


// --- Функция покупки товара (Stripe Checkout) ---
async function buyProduct(productId) {
    const token = localStorage.getItem('accessToken')
    if (!token) {
        alert("Пожалуйста, авторизуйтесь для покупки.")
        return
    }

    try {
        // Дергаем наш новый роутер FastAPI
        const response = await fetch(`${API_URL}/payment/checkout/${productId}`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        })

        const data = await response.json()

        if (response.ok) {
            // МАГИЯ ЗДЕСЬ: перенаправляем браузер на защищенную страницу Stripe
            window.location.href = data.checkout_url
        } else {
            alert('Ошибка покупки: ' + (data.detail || "Неизвестная ошибка"))
        }
    } catch (error) {
        alert("Ошибка сети: " + error)
    }
}
