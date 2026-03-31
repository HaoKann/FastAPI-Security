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
                
                // Меняем докеровский адрес на локальный, чтобы браузер понял, откуда качать
                if (finalAvatarUrl.includes('minio:9000')) {
                    finalAvatarUrl = finalAvatarUrl.replace('minio:9000', 'localhost:9000')
                }

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

// --- ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ДЛЯ ПАГИНАЦИИ ---
let currentOffset = 0
const LIMIT = 2 // Выводим по 2 товара на страницу для наглядности

// --- 4. Функция получения товаров с токеном---
async function getProducts() {
    const token = localStorage.getItem('accessToken') // <-- 1. Достаем токен
    const responseArea = document.getElementById('response-area')

    try {
        const response = await fetch(`${API_URL}/products/?limit=${LIMIT}&offset=${currentOffset}`, {
            method: 'GET',
            headers: {
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

       // РИСУЕМ КРАСИВЫЕ КАРТОЧКИ С КНОПКАМИ! 🎨
        let html = `
            <h3 style="margin-bottom: 15px; color: #667eea;">📦 Витрина товаров</h3>
            <div style="display: flex; flex-wrap: wrap; gap: 15px;">
        `;
        
        if (products.length === 0 && currentOffset === 0) {
            html += `<p style="color: #718096; width: 100%;">У вас пока нет ни одного товара.</p>`;
        } else if (products.length === 0) {
            html += `<p style="color: #718096; width: 100%;">Больше товаров нет.</p>`;
        } else {
            products.forEach(p => {
                html += `
                <div style="background: white; border: 2px solid #edf2f7; border-radius: 12px; padding: 20px; width: 220px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); transition: transform 0.2s; display: flex; flex-direction: column;">
                    <h4 style="margin-bottom: 10px; color: #2d3748; font-size: 1.2em;">${p.name}</h4>
                    <p style="color: #48bb78; font-weight: 800; font-size: 1.4em; margin-bottom: 5px;">$${p.price}</p>
                    
                    <p style="color: #ed8936; font-size: 0.85em; margin-bottom: 10px; font-weight: bold;">
                        С налогом: $${p.price_with_tax}
                    </p>

                    <div style="margin-bottom: 15px;">
                        <span style="background: #edf2f7; color: #4a5568; padding: 4px 8px; border-radius: 6px; font-size: 0.8em;">ID: ${p.id.substring(0,6)}...</span>
                    </div>
                    <div style="margin-top: auto; display: flex; gap: 8px;">
                        <button onclick="editProduct('${p.id}', '${p.name}', ${p.price})" style="background: #cbd5e0; color: #2d3748; padding: 6px 10px; font-size: 0.9em; flex: 1; border-radius: 6px; border: none; cursor: pointer;">✏️ Цена</button>
                        <button onclick="deleteProduct('${p.id}')" style="background: #fc8181; color: white; padding: 6px 10px; font-size: 0.9em; flex: 1; border-radius: 6px; border: none; cursor: pointer;">🗑️ Удал.</button>
                    </div>
                </div>
                `;
            });
        }
        html += `</div>`;

        // Кнопки пагинации
        const currentPage = (currentOffset / LIMIT) + 1
        const isLastPage = products.length < LIMIT // Если пришло меньше 2 товаров, значит это конец
        
        html += `
        <div style="margin-top: 25px; display: flex; gap: 15px; align-items: center; justify-content: center; width: 100%; max-width: 450px;">
            <button onclick="prevPage()" ${currentOffset === 0 ? 'disabled' : ''} 
                    style="padding: 10px 20px; border-radius: 8px; border: none; font-weight: bold; transition: 0.2s;
                           background: ${currentOffset === 0 ? '#e2e8f0' : '#667eea'}; 
                           color: ${currentOffset === 0 ? '#a0aec0' : 'white'}; 
                           cursor: ${currentOffset === 0 ? 'not-allowed' : 'pointer'};">
                ⬅️ Назад
            </button>

            <span style="color: #4a5568; font-weight: bold; font-size: 1.1em;">
                Страница ${currentPage}
            </span>

            <button onclick="nextPage(${isLastPage})" ${isLastPage ? 'disabled' : ''} 
                    style="padding: 10px 20px; border-radius: 8px; border: none; font-weight: bold; transition: 0.2s;
                           background: ${isLastPage ? '#e2e8f0' : '#667eea'}; 
                           color: ${isLastPage ? '#a0aec0' : 'white'}; 
                           cursor: ${isLastPage ? 'not-allowed' : 'pointer'};">
                Вперед ➡️
            </button>
        </div>
        `;

        responseArea.innerHTML = html;
        
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
