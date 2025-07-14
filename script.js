// Инициализация Telegram Web App
let tg = window.Telegram.WebApp;
tg.expand();
tg.ready();

// Настройка темы
tg.setHeaderColor('#667eea');
tg.setBackgroundColor('#667eea');

// Глобальные переменные
let currentQuiz = null;
let currentDifficulty = null;
let currentGameMode = 'normal';
let currentQuestionIndex = 0;
let score = 0;
let questions = [];
let totalQuestions = 0;
let hintsUsed = 0;
let maxHints = 2;
let gameStartTime = null;
let questionStartTime = null;
let userProfile = null;

// Получение данных пользователя Telegram
const userId = tg.initDataUnsafe?.user?.id || `demo_${Date.now()}`;
const userName = tg.initDataUnsafe?.user?.username || '';
const firstName = tg.initDataUnsafe?.user?.first_name || 'Игрок';
const lastName = tg.initDataUnsafe?.user?.last_name || '';

// Информация о категориях с расширенными данными
const categoryInfo = {
    'history': { 
        name: 'История', 
        emoji: '🏛', 
        color: '#f093fb',
        description: 'События прошлого, великие личности'
    },
    'science': { 
        name: 'Наука', 
        emoji: '🔬', 
        color: '#4facfe',
        description: 'Физика, химия, биология, открытия'
    },
    'geography': { 
        name: 'География', 
        emoji: '🌍', 
        color: '#43e97b',
        description: 'Страны, столицы, природа'
    },
    'sports': { 
        name: 'Спорт', 
        emoji: '⚽', 
        color: '#fa709a',
        description: 'Олимпиада, чемпионаты, рекорды'
    },
    'technology': { 
        name: 'Технологии', 
        emoji: '💻', 
        color: '#43cbff',
        description: 'IT, изобретения, будущее'
    },
    'arts': { 
        name: 'Искусство', 
        emoji: '🎨', 
        color: '#f8b500',
        description: 'Живопись, музыка, литература'
    }
};

const difficultyInfo = {
    'easy': { name: 'Легкий', emoji: '🟢', points: 10 },
    'medium': { name: 'Средний', emoji: '🟡', points: 20 },
    'hard': { name: 'Сложный', emoji: '🔴', points: 30 }
};

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', () => {
    console.log('🧠 Enhanced Quiz Mini App загружен');
    console.log('👤 Пользователь:', firstName, '(ID:', userId, ')');
    
    // Обновляем имя пользователя в интерфейсе
    updateUserGreeting();
    
    // Загружаем категории
    loadCategories();
    
    // Загружаем профиль пользователя
    loadUserProfile();
    
    // Загружаем ежедневное задание
    loadDailyChallenge();
    
    // Загружаем рейтинг
    loadLeaderboard();
    
    // Проверяем соединение с сервером
    fetch('/health')
        .then(response => response.json())
        .then(data => {
            console.log('✅ Соединение с сервером установлено:', data);
        })
        .catch(error => {
            console.error('❌ Ошибка соединения:', error);
        });
});

// Обновление приветствия
function updateUserGreeting() {
    document.getElementById('userName').textContent = firstName;
    const resultPlayerName = document.getElementById('resultsPlayerName');
    if (resultPlayerName) {
        resultPlayerName.textContent = firstName;
    }
}

// Загрузка категорий
function loadCategories() {
    const container = document.getElementById('categoriesContainer');
    const categoriesHTML = `
        <h3>📚 Выберите категорию</h3>
        <div class="category-grid">
            ${Object.entries(categoryInfo).map(([key, info]) => `
                <div class="category-card" onclick="selectCategory('${key}')">
                    <span class="category-icon">${info.emoji}</span>
                    <div class="category-name">${info.name}</div>
                    <div class="category-count">Множество вопросов</div>
                </div>
            `).join('')}
        </div>
    `;
    container.innerHTML = categoriesHTML;
}

// Навигация между экранами
function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(screen => {
        screen.classList.remove('active');
    });
    
    document.getElementById(screenId).classList.add('active');
    
    // Настройка кнопки "Назад" в Telegram
    if (screenId === 'mainMenu') {
        tg.BackButton.hide();
    } else {
        tg.BackButton.show();
    }
    
    // Haptic feedback
    tg.HapticFeedback.impactOccurred('light');
}

// Переключение вкладок
function showTab(tabName) {
    // Убираем active у всех кнопок табов
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Убираем active у всех табов
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    
    // Добавляем active к выбранным
    document.querySelector(`[onclick="showTab('${tabName}')"]`).classList.add('active');
    document.getElementById(`${tabName}Tab`).classList.add('active');
    
    // Загружаем данные для вкладки
    if (tabName === 'profile') {
        loadUserProfile();
    } else if (tabName === 'leaderboard') {
        loadLeaderboard();
    }
    
    tg.HapticFeedback.impactOccurred('light');
}

// Выбор режима игры
function selectGameMode(mode) {
    currentGameMode = mode;
    
    if (mode === 'marathon') {
        // Для марафона сразу начинаем игру со смешанными вопросами
        startMarathonQuiz();
    } else {
        // Для обычного режима показываем выбор категории (уже показан)
        tg.HapticFeedback.impactOccurred('medium');
    }
}

// Выбор категории
function selectCategory(category) {
    currentQuiz = category;
    
    if (currentGameMode === 'normal') {
        // Показываем экран выбора сложности
        showDifficultyScreen(category);
    }
    
    tg.HapticFeedback.impactOccurred('medium');
}

// Показ экрана выбора сложности
function showDifficultyScreen(category) {
    const categoryData = categoryInfo[category];
    document.getElementById('selectedCategory').textContent = categoryData.name;
    showScreen('difficultyScreen');
}

// Начало обычной викторины
async function startQuiz(difficulty) {
    currentDifficulty = difficulty;
    await loadAndStartQuiz(currentQuiz, difficulty);
}

// Начало марафона
async function startMarathonQuiz() {
    currentDifficulty = 'mixed';
    currentGameMode = 'marathon';
    
    showScreen('loadingScreen');
    updateLoadingScreen('Подготовка марафона...', 'Собираем лучшие вопросы из всех категорий');
    
    try {
        // Загружаем вопросы из всех категорий и сложностей
        const allQuestions = [];
        
        for (const [category, difficulties] of Object.entries(categoryInfo)) {
            for (const diff of ['easy', 'medium', 'hard']) {
                try {
                    const response = await fetch(`/api/questions/${category}/${diff}`);
                    if (response.ok) {
                        const categoryQuestions = await response.json();
                        // Добавляем метаданные к каждому вопросу
                        categoryQuestions.forEach(q => {
                            q.category = category;
                            q.difficulty = diff;
                        });
                        allQuestions.push(...categoryQuestions);
                    }
                } catch (error) {
                    console.warn(`Не удалось загрузить ${category}/${diff}:`, error);
                }
            }
        }
        
        if (allQuestions.length === 0) {
            throw new Error('Вопросы не найдены');
        }
        
        // Перемешиваем и берем 20 вопросов
        questions = shuffleArray(allQuestions).slice(0, 20);
        totalQuestions = questions.length;
        
        // Сброс игровых переменных
        currentQuestionIndex = 0;
        score = 0;
        hintsUsed = 0;
        gameStartTime = Date.now();
        
        // Обновляем интерфейс для марафона
        document.getElementById('currentCategory').textContent = '🏃‍♂️ Марафон';
        document.getElementById('currentDifficulty').textContent = '🌈 Смешанная';
        
        showScreen('quizScreen');
        showQuestion();
        
        tg.HapticFeedback.notificationOccurred('success');
        
    } catch (error) {
        console.error('Ошибка запуска марафона:', error);
        tg.showAlert('Ошибка загрузки вопросов для марафона. Попробуйте позже.');
        showMainMenu();
    }
}

// Загрузка и начало обычной викторины
async function loadAndStartQuiz(category, difficulty) {
    try {
        showScreen('loadingScreen');
        updateLoadingScreen('Загрузка вопросов...', `Подготавливаем ${difficultyInfo[difficulty].name.toLowerCase()} уровень`);
        
        const response = await fetch(`/api/questions/${category}/${difficulty}`);
        if (!response.ok) {
            throw new Error('Ошибка загрузки вопросов');
        }
        
        questions = await response.json();
        
        if (questions.length === 0) {
            throw new Error('Вопросы не найдены');
        }
        
        // Инициализация игры
        totalQuestions = questions.length;
        currentQuestionIndex = 0;
        score = 0;
        hintsUsed = 0;
        gameStartTime = Date.now();
        
        // Обновляем информацию о категории и сложности
        const categoryData = categoryInfo[category];
        const difficultyData = difficultyInfo[difficulty];
        
        document.getElementById('currentCategory').textContent = `${categoryData.emoji} ${categoryData.name}`;
        document.getElementById('currentDifficulty').textContent = `${difficultyData.emoji} ${difficultyData.name}`;
        
        showScreen('quizScreen');
        showQuestion();
        
        tg.HapticFeedback.notificationOccurred('success');
        
    } catch (error) {
        console.error('Ошибка запуска викторины:', error);
        tg.showAlert('Ошибка загрузки вопросов. Попробуйте еще раз.');
        showMainMenu();
    }
}

// Обновление экрана загрузки
function updateLoadingScreen(title, subtitle) {
    document.getElementById('loadingTitle').textContent = title;
    document.getElementById('loadingSubtitle').textContent = subtitle;
    
    // Случайные факты для загрузки
    const tips = [
        "💡 Регулярные интеллектуальные упражнения улучшают память и концентрацию",
        "🧠 Человеческий мозг содержит около 86 миллиардов нейронов",
        "📚 Чтение и решение головоломок помогают предотвратить старение мозга",
        "🎯 Викторины развивают критическое мышление и логику",
        "⚡ Мозг потребляет около 20% всей энергии организма",
        "🌟 Изучение новой информации создает новые нейронные связи"
    ];
    
    const randomTip = tips[Math.floor(Math.random() * tips.length)];
    document.getElementById('loadingTip').textContent = randomTip;
}

// Показ текущего вопроса
function showQuestion() {
    const question = questions[currentQuestionIndex];
    questionStartTime = Date.now();
    
    // Обновляем прогресс
    const progress = ((currentQuestionIndex + 1) / totalQuestions) * 100;
    document.getElementById('progress').style.width = progress + '%';
    
    // Обновляем информацию
    document.getElementById('questionNumber').textContent = `${currentQuestionIndex + 1}/${totalQuestions}`;
    document.getElementById('score').textContent = `Счет: ${score}`;
    document.getElementById('questionText').textContent = question.question;
    
    // Обновляем таймер (если нужно)
    updateTimer();
    
    // Создаем кнопки ответов
    const answersContainer = document.getElementById('answers');
    answersContainer.innerHTML = '';
    
    question.options.forEach((option, index) => {
        const button = document.createElement('button');
        button.className = 'answer-btn';
        button.textContent = option;
        button.onclick = () => selectAnswer(index);
        button.id = `answer-${index}`;
        answersContainer.appendChild(button);
    });
    
    // Скрываем объяснение и кнопку "Далее"
    document.getElementById('explanation').style.display = 'none';
    document.getElementById('nextBtn').style.display = 'none';
    
    // Обновляем счетчик подсказок
    document.getElementById('hintsLeft').textContent = maxHints - hintsUsed;
    
    // Блокируем использованные подсказки
    if (hintsUsed >= maxHints) {
        document.getElementById('hint5050').disabled = true;
        document.getElementById('hintSkip').disabled = true;
    }
}

// Выбор ответа
function selectAnswer(selectedIndex) {
    const question = questions[currentQuestionIndex];
    const buttons = document.querySelectorAll('.answer-btn');
    const answerTime = Date.now() - questionStartTime;
    
    // Отключаем все кнопки
    buttons.forEach(btn => {
        btn.classList.add('disabled');
        btn.onclick = null;
    });
    
    // Показываем правильный и неправильный ответы
    buttons.forEach((btn, index) => {
        if (index === question.correct) {
            btn.classList.add('correct');
        } else if (index === selectedIndex && index !== question.correct) {
            btn.classList.add('incorrect');
        }
    });
    
    // Проверяем ответ
    const isCorrect = selectedIndex === question.correct;
    if (isCorrect) {
        score++;
        tg.HapticFeedback.notificationOccurred('success');
    } else {
        tg.HapticFeedback.notificationOccurred('error');
    }
    
    // Обновляем счет
    document.getElementById('score').textContent = `Счет: ${score}`;
    
    // Показываем объяснение, если есть
    if (question.explanation) {
        document.getElementById('explanationText').textContent = question.explanation;
        document.getElementById('explanation').style.display = 'block';
    }
    
    // Показываем кнопку "Далее" с задержкой
    setTimeout(() => {
        document.getElementById('nextBtn').style.display = 'block';
    }, 1500);
}

// Использование подсказки
function useHint(hintType) {
    if (hintsUsed >= maxHints) {
        tg.showAlert('Подсказки закончились!');
        return;
    }
    
    const question = questions[currentQuestionIndex];
    const buttons = document.querySelectorAll('.answer-btn');
    
    if (hintType === '5050') {
        // Убираем 2 неправильных ответа
        let removedCount = 0;
        buttons.forEach((btn, index) => {
            if (index !== question.correct && removedCount < 2) {
                btn.classList.add('hidden');
                btn.onclick = null;
                removedCount++;
            }
        });
        
        document.getElementById('hint5050').disabled = true;
        tg.HapticFeedback.impactOccurred('medium');
        
    } else if (hintType === 'skip') {
        // Пропускаем вопрос
        tg.showConfirm('Пропустить этот вопрос?', (confirmed) => {
            if (confirmed) {
                nextQuestion();
            }
        });
        return; // Не увеличиваем счетчик, если пользователь отменил
    }
    
    hintsUsed++;
    document.getElementById('hintsLeft').textContent = maxHints - hintsUsed;
    
    if (hintsUsed >= maxHints) {
        document.getElementById('hint5050').disabled = true;
        document.getElementById('hintSkip').disabled = true;
    }
}

// Следующий вопрос
function nextQuestion() {
    currentQuestionIndex++;
    
    if (currentQuestionIndex >= totalQuestions) {
        endQuiz();
    } else {
        showQuestion();
        tg.HapticFeedback.impactOccurred('light');
    }
}

// Завершение викторины
async function endQuiz() {
    const gameEndTime = Date.now();
    const totalTime = Math.round((gameEndTime - gameStartTime) / 1000); // в секундах
    const percentage = Math.round((score / totalQuestions) * 100);
    
    // Определяем оценку и сообщение
    let grade, message, hapticType;
    if (percentage >= 90) {
        grade = "🏆 Превосходно!";
        message = "Невероятный результат! Вы настоящий эксперт!";
        hapticType = 'success';
    } else if (percentage >= 80) {
        grade = "🥇 Отлично!";
        message = "Фантастическая работа! Вы очень эрудированы!";
        hapticType = 'success';
    } else if (percentage >= 70) {
        grade = "🥈 Очень хорошо!";
        message = "Отличный результат! Продолжайте в том же духе!";
        hapticType = 'success';
    } else if (percentage >= 60) {
        grade = "🥉 Хорошо!";
        message = "Неплохой результат! Есть к чему стремиться!";
        hapticType = 'warning';
    } else if (percentage >= 40) {
        grade = "📚 Удовлетворительно";
        message = "Базовые знания есть, но стоит подтянуть теорию!";
        hapticType = 'warning';
    } else {
        grade = "💪 Не сдавайтесь!";
        message = "Учитесь дальше, и результат обязательно улучшится!";
        hapticType = 'error';
    }
    
    // Форматируем время
    const timeString = formatTime(totalTime);
    
    // Показываем результаты
    document.getElementById('finalScore').textContent = `${score}/${totalQuestions}`;
    document.getElementById('finalPercentage').textContent = `${percentage}%`;
    document.getElementById('resultGrade').textContent = grade;
    document.getElementById('resultMessage').textContent = message;
    document.getElementById('resultTime').textContent = timeString;
    document.getElementById('resultHints').textContent = hintsUsed === 0 ? 'Не использовано' : `${hintsUsed} использовано`;
    
    // Показываем категорию и сложность
    if (currentGameMode === 'marathon') {
        document.getElementById('resultCategory').textContent = '🏃‍♂️ Марафон';
        document.getElementById('resultDifficulty').textContent = '🌈 Смешанная';
    } else {
        const categoryData = categoryInfo[currentQuiz];
        const difficultyData = difficultyInfo[currentDifficulty];
        document.getElementById('resultCategory').textContent = `${categoryData.emoji} ${categoryData.name}`;
        document.getElementById('resultDifficulty').textContent = `${difficultyData.emoji} ${difficultyData.name}`;
    }
    
    // Сохраняем результат и проверяем достижения
    try {
        const response = await fetch('/api/save_game', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user_id: userId,
                username: userName,
                first_name: firstName,
                last_name: lastName,
                score: score,
                total: totalQuestions,
                category: currentQuiz || 'mixed',
                difficulty: currentDifficulty,
                time_spent: totalTime,
                hints_used: hintsUsed,
                game_mode: currentGameMode
            })
        });
        
        if (response.ok) {
            const result = await response.json();
            
            // Показываем новые достижения
            if (result.new_achievements && result.new_achievements.length > 0) {
                showNewAchievements(result.new_achievements);
            }
        }
    } catch (error) {
        console.error('Ошибка сохранения результата:', error);
    }
    
    // Haptic feedback
    tg.HapticFeedback.notificationOccurred(hapticType);
    
    showScreen('resultsScreen');
}

// Показ новых достижений
function showNewAchievements(achievements) {
    const container = document.getElementById('newAchievements');
    const list = container.querySelector('.achievements-list');
    
    list.innerHTML = achievements.map(ach => `
        <div class="new-achievement-item bounce">
            <div class="new-achievement-icon">${ach.icon}</div>
            <div class="new-achievement-info">
                <h4>${ach.name}</h4>
                <p>${ach.description} (+${ach.points} очков)</p>
            </div>
        </div>
    `).join('');
    
    container.style.display = 'block';
    
    // Показываем уведомление в Telegram
    if (achievements.length === 1) {
        tg.showAlert(`🎉 Новое достижение: ${achievements[0].name}!`);
    } else {
        tg.showAlert(`🎉 Получено достижений: ${achievements.length}!`);
    }
}

// Загрузка профиля пользователя
async function loadUserProfile() {
    try {
        const response = await fetch(`/api/profile/${userId}`);
        if (response.ok) {
            userProfile = await response.json();
            updateProfileDisplay();
        }
    } catch (error) {
        console.error('Ошибка загрузки профиля:', error);
    }
}

// Обновление отображения профиля
function updateProfileDisplay() {
    if (!userProfile) return;
    
    const profile = userProfile.profile;
    
    // Обновляем имя и статистику
    document.getElementById('profileName').textContent = 
        `${profile.first_name} ${profile.last_name || ''}`.trim();
    document.getElementById('profileStats').textContent = 
        `${profile.total_games} игр • Лучшая серия: ${profile.best_streak}`;
    
    // Достижения
    const achievementsList = document.getElementById('achievementsList');
    achievementsList.innerHTML = userProfile.achievements.map(ach => `
        <div class="achievement-item ${ach.unlocked ? 'unlocked' : 'locked'}">
            <span class="achievement-icon">${ach.icon}</span>
            <div class="achievement-name">${ach.name}</div>
            <div class="achievement-desc">${ach.description}</div>
        </div>
    `).join('');
    
    // Статистика по категориям
    const statsContainer = document.getElementById('categoryStats');
    if (userProfile.category_stats.length === 0) {
        statsContainer.innerHTML = '<p style="text-align: center; color: #666; padding: 20px;">Сыграйте первую игру, чтобы увидеть статистику</p>';
    } else {
        statsContainer.innerHTML = userProfile.category_stats.map(stat => {
            const categoryData = categoryInfo[stat.category];
            return `
                <div class="stat-item">
                    <div class="stat-header">
                        <span class="stat-category">${categoryData.emoji} ${categoryData.name}</span>
                    </div>
                    <div class="stat-details">
                        <div class="stat-detail">
                            <span class="stat-value">${stat.games}</span>
                            <span class="stat-label">игр</span>
                        </div>
                        <div class="stat-detail">
                            <span class="stat-value">${stat.avg_score}%</span>
                            <span class="stat-label">средний</span>
                        </div>
                        <div class="stat-detail">
                            <span class="stat-value">${stat.best_score}%</span>
                            <span class="stat-label">лучший</span>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }
}

// Загрузка рейтинга
async function loadLeaderboard() {
    const category = document.getElementById('leaderboardCategory').value;
    
    try {
        const response = await fetch(`/api/leaderboard/${category}`);
        if (response.ok) {
            const leaderboard = await response.json();
            updateLeaderboardDisplay(leaderboard);
        }
    } catch (error) {
        console.error('Ошибка загрузки рейтинга:', error);
    }
}

// Обновление отображения рейтинга
function updateLeaderboardDisplay(leaderboard) {
    const container = document.getElementById('leaderboardList');
    
    if (leaderboard.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #666; padding: 20px;">Рейтинг пуст</p>';
        return;
    }
    
    container.innerHTML = leaderboard.map((player, index) => {
        const medals = ['🥇', '🥈', '🥉'];
        const rank = index < 3 ? medals[index] : (index + 1);
        const isCurrentUser = player.user_id === userId;
        
        return `
            <div class="leaderboard-item ${isCurrentUser ? 'current-user' : ''}">
                <div class="rank ${index < 3 ? 'medal' : ''}">${rank}</div>
                <div class="player-info">
                    <div class="player-name">${player.first_name} ${isCurrentUser ? '(Вы)' : ''}</div>
                    <div class="player-stats">${player.games} игр • Лучший: ${player.best_score}%</div>
                </div>
                <div class="player-score">${player.avg_score}%</div>
            </div>
        `;
    }).join('');
}

// Загрузка ежедневного задания
async function loadDailyChallenge() {
    try {
        const response = await fetch(`/api/daily_challenge/${userId}`);
        if (response.ok) {
            const challenge = await response.json();
            updateDailyChallengeDisplay(challenge);
        }
    } catch (error) {
        console.error('Ошибка загрузки ежедневного задания:', error);
    }
}

// Обновление отображения ежедневного задания
function updateDailyChallengeDisplay(challenge) {
    document.getElementById('challengeText').textContent = challenge.description;
    document.getElementById('challengeStatus').textContent = `${challenge.progress}/${challenge.target}`;
    
    const progress = (challenge.progress / challenge.target) * 100;
    document.getElementById('challengeProgress').style.width = `${Math.min(progress, 100)}%`;
    
    if (challenge.completed) {
        document.getElementById('challengeText').textContent += ' ✅ Выполнено!';
        document.querySelector('.daily-challenge').style.background = 
            'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)';
    }
}

// Поделиться результатом
function shareResult() {
    const score = document.getElementById('finalScore').textContent;
    const percentage = document.getElementById('finalPercentage').textContent;
    const category = document.getElementById('resultCategory').textContent;
    
    const shareText = `🧠 Я прошел викторину!\n\n` +
                     `📊 Результат: ${score} (${percentage})\n` +
                     `📚 Категория: ${category}\n\n` +
                     `Попробуйте и вы! 🎯`;
    
    if (navigator.share) {
        navigator.share({
            title: 'Результат викторины',
            text: shareText
        });
    } else {
        // Fallback для копирования в буфер обмена
        navigator.clipboard.writeText(shareText).then(() => {
            tg.showAlert('Результат скопирован в буфер обмена!');
        });
    }
}

// Возврат в главное меню
function showMainMenu() {
    showScreen('mainMenu');
    showTab('categories');
    
    // Сбрасываем игровые переменные
    currentQuiz = null;
    currentDifficulty = null;
    currentGameMode = 'normal';
    hintsUsed = 0;
    
    // Перезагружаем профиль и задания
    loadUserProfile();
    loadDailyChallenge();
}

// Обработчики Telegram
tg.BackButton.onClick(() => {
    const currentScreen = document.querySelector('.screen.active').id;
    
    if (currentScreen === 'quizScreen') {
        tg.showConfirm('Вы действительно хотите прервать игру?', (confirmed) => {
            if (confirmed) {
                showMainMenu();
            }
        });
    } else if (currentScreen === 'difficultyScreen') {
        showMainMenu();
    } else {
        showMainMenu();
    }
});

// Утилиты
function shuffleArray(array) {
    const shuffled = [...array];
    for (let i = shuffled.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    return shuffled;
}

function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
}

// Таймер (опционально)
let timerInterval = null;

function updateTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
    }
    
    let timeLeft = 30; // 30 секунд на вопрос
    const timerElement = document.getElementById('timer');
    
    timerInterval = setInterval(() => {
        timeLeft--;
        const minutes = Math.floor(timeLeft / 60);
        const seconds = timeLeft % 60;
        timerElement.textContent = `⏱ ${minutes}:${seconds.toString().padStart(2, '0')}`;
        
        if (timeLeft <= 0) {
            clearInterval(timerInterval);
            // Автоматически пропускаем вопрос при истечении времени
            tg.showAlert('Время вышло!');
            setTimeout(nextQuestion, 1000);
        }
    }, 1000);
}
