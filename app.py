# -*- coding: utf-8 -*-
"""
Enhanced Quiz Mini App - Полнофункциональное приложение-викторина для Telegram
Поддержка: профили, достижения, рейтинг, ежедневные задания
"""

from flask import Flask, render_template, jsonify, request, send_from_directory, g
import json
import sqlite3
import os
import random
import logging
import hashlib
import hmac
import urllib.parse
from datetime import datetime, date, timedelta
from functools import wraps
from contextlib import closing
import traceback

# =====================================
# КОНФИГУРАЦИЯ ПРИЛОЖЕНИЯ
# =====================================

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.config['JSON_SORT_KEYS'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

# Настройки
DEBUG = os.environ.get('FLASK_ENV') == 'development'
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
DATABASE_PATH = 'quiz_scores.db'
QUESTIONS_FILE = 'questions.json'

# =====================================
# НАСТРОЙКА ЛОГИРОВАНИЯ
# =====================================

logging.basicConfig(
    level=logging.INFO if not DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

# =====================================
# ДЕКОРАТОРЫ И УТИЛИТЫ
# =====================================

def handle_db_error(f):
    """Декоратор для обработки ошибок базы данных"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except sqlite3.Error as e:
            logger.error(f"Database error in {f.__name__}: {e}")
            return jsonify({'error': 'Database error', 'message': str(e)}), 500
        except Exception as e:
            logger.error(f"Error in {f.__name__}: {e}")
            logger.error(traceback.format_exc())
            return jsonify({'error': 'Internal error', 'message': str(e)}), 500
    return decorated_function

def get_db():
    """Получение соединения с базой данных"""
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(error):
    """Закрытие соединения с базой данных"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

app.teardown_appcontext(close_db)

def validate_telegram_data(init_data, bot_token):
    """Валидация данных от Telegram Web App"""
    try:
        if not init_data or not bot_token:
            return False
            
        parsed_data = urllib.parse.parse_qs(init_data)
        
        # Извлекаем хеш
        received_hash = parsed_data.get('hash', [None])[0]
        if not received_hash:
            return False
        
        # Создаем строку для проверки
        data_check_string = '\n'.join([
            f"{key}={value[0]}" 
            for key, value in sorted(parsed_data.items()) 
            if key != 'hash'
        ])
        
        # Создаем секретный ключ
        secret_key = hmac.new(
            b'WebAppData', 
            bot_token.encode(), 
            hashlib.sha256
        ).digest()
        
        # Вычисляем хеш
        calculated_hash = hmac.new(
            secret_key, 
            data_check_string.encode(), 
            hashlib.sha256
        ).hexdigest()
        
        return calculated_hash == received_hash
        
    except Exception as e:
        logger.warning(f"Telegram data validation error: {e}")
        return False

# =====================================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ
# =====================================

def init_database():
    """Инициализация базы данных со всеми таблицами"""
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            
            # Таблица результатов игр
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS game_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    score INTEGER NOT NULL,
                    total INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    difficulty TEXT NOT NULL,
                    percentage REAL NOT NULL,
                    time_spent INTEGER DEFAULT 0,
                    hints_used INTEGER DEFAULT 0,
                    game_mode TEXT DEFAULT 'normal',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Индекс для быстрого поиска по пользователю
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_game_results_user_id 
                ON game_results(user_id)
            ''')
            
            # Таблица профилей игроков
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT NOT NULL,
                    last_name TEXT,
                    total_games INTEGER DEFAULT 0,
                    total_score INTEGER DEFAULT 0,
                    best_streak INTEGER DEFAULT 0,
                    current_streak INTEGER DEFAULT 0,
                    achievements TEXT DEFAULT '[]',
                    favorite_category TEXT,
                    level INTEGER DEFAULT 1,
                    experience_points INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица ежедневных заданий
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_challenges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    challenge_date DATE NOT NULL,
                    challenge_type TEXT NOT NULL,
                    target_value INTEGER NOT NULL,
                    current_progress INTEGER DEFAULT 0,
                    completed BOOLEAN DEFAULT FALSE,
                    reward_claimed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, challenge_date, challenge_type)
                )
            ''')
            
            # Таблица достижений
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS achievements (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    icon TEXT NOT NULL,
                    condition_type TEXT NOT NULL,
                    condition_value INTEGER NOT NULL,
                    reward_points INTEGER DEFAULT 0,
                    rarity TEXT DEFAULT 'common'
                )
            ''')
            
            # Таблица статистики приложения
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS app_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    total_users INTEGER DEFAULT 0,
                    total_games INTEGER DEFAULT 0,
                    total_questions_answered INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            logger.info("✅ База данных инициализирована успешно")
            
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации базы данных: {e}")
        raise

def init_achievements():
    """Инициализация стандартных достижений"""
    achievements = [
        {
            'id': 'first_game',
            'name': 'Первые шаги',
            'description': 'Завершите первую игру',
            'icon': '🎯',
            'condition_type': 'games_played',
            'condition_value': 1,
            'reward_points': 10,
            'rarity': 'common'
        },
        {
            'id': 'perfectionist',
            'name': 'Перфекционист',
            'description': 'Ответьте правильно на все вопросы в игре',
            'icon': '💯',
            'condition_type': 'perfect_score',
            'condition_value': 1,
            'reward_points': 50,
            'rarity': 'rare'
        },
        {
            'id': 'scholar',
            'name': 'Эрудит',
            'description': 'Наберите 80%+ в трех разных категориях',
            'icon': '🎓',
            'condition_type': 'category_master',
            'condition_value': 3,
            'reward_points': 100,
            'rarity': 'epic'
        },
        {
            'id': 'marathoner',
            'name': 'Марафонец',
            'description': 'Завершите режим марафон',
            'icon': '🏃‍♂️',
            'condition_type': 'marathon_completed',
            'condition_value': 1,
            'reward_points': 75,
            'rarity': 'rare'
        },
        {
            'id': 'streak_master',
            'name': 'Мастер серий',
            'description': 'Ответьте правильно на 10 вопросов подряд',
            'icon': '🔥',
            'condition_type': 'answer_streak',
            'condition_value': 10,
            'reward_points': 80,
            'rarity': 'rare'
        },
        {
            'id': 'speed_demon',
            'name': 'Скоростной демон',
            'description': 'Завершите игру менее чем за 2 минуты',
            'icon': '⚡',
            'condition_type': 'speed_completion',
            'condition_value': 120,
            'reward_points': 60,
            'rarity': 'uncommon'
        },
        {
            'id': 'dedicated_player',
            'name': 'Преданный игрок',
            'description': 'Играйте 7 дней подряд',
            'icon': '📅',
            'condition_type': 'daily_streak',
            'condition_value': 7,
            'reward_points': 150,
            'rarity': 'epic'
        },
        {
            'id': 'knowledge_seeker',
            'name': 'Искатель знаний',
            'description': 'Сыграйте 100 игр',
            'icon': '📚',
            'condition_type': 'games_played',
            'condition_value': 100,
            'reward_points': 200,
            'rarity': 'legendary'
        }
    ]
    
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            
            for ach in achievements:
                cursor.execute('''
                    INSERT OR REPLACE INTO achievements 
                    (id, name, description, icon, condition_type, condition_value, reward_points, rarity)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    ach['id'], ach['name'], ach['description'], ach['icon'],
                    ach['condition_type'], ach['condition_value'], 
                    ach['reward_points'], ach['rarity']
                ))
            
            conn.commit()
            logger.info(f"✅ Инициализировано {len(achievements)} достижений")
            
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации достижений: {e}")

def create_questions_file():
    """Создание файла с вопросами"""
    questions = {
        "history": {
            "easy": [
                {
                    "question": "В каком году началась Вторая мировая война?",
                    "options": ["1939", "1940", "1941", "1938"],
                    "correct": 0,
                    "explanation": "Вторая мировая война началась 1 сентября 1939 года с нападения Германии на Польшу."
                },
                {
                    "question": "Кто был первым президентом США?",
                    "options": ["Томас Джефферсон", "Джордж Вашингтон", "Джон Адамс", "Бенджамин Франклин"],
                    "correct": 1,
                    "explanation": "Джордж Вашингтон был первым президентом США (1789-1797)."
                },
                {
                    "question": "В каком году пала Берлинская стена?",
                    "options": ["1987", "1988", "1989", "1990"],
                    "correct": 2,
                    "explanation": "Берлинская стена была разрушена 9 ноября 1989 года."
                },
                {
                    "question": "Кто открыл Америку для европейцев?",
                    "options": ["Васко да Гама", "Христофор Колумб", "Фернан Магеллан", "Америго Веспуччи"],
                    "correct": 1,
                    "explanation": "Христофор Колумб открыл Америку для европейцев в 1492 году."
                },
                {
                    "question": "В каком году по легенде был основан Рим?",
                    "options": ["753 до н.э.", "776 до н.э.", "500 до н.э.", "800 до н.э."],
                    "correct": 0,
                    "explanation": "По легенде, Рим был основан Ромулом в 753 году до н.э."
                },
                {
                    "question": "Какая династия правила в России до Романовых?",
                    "options": ["Годуновы", "Рюриковичи", "Шуйские", "Голицыны"],
                    "correct": 1,
                    "explanation": "Династия Рюриковичей правила в России до прихода к власти Романовых."
                }
            ],
            "medium": [
                {
                    "question": "Какая битва считается поворотным моментом в Великой Отечественной войне?",
                    "options": ["Битва за Москву", "Сталинградская битва", "Курская битва", "Битва за Ленинград"],
                    "correct": 1,
                    "explanation": "Сталинградская битва (1942-1943) стала переломным моментом в войне."
                },
                {
                    "question": "В каком году произошла Октябрьская революция в России?",
                    "options": ["1916", "1917", "1918", "1919"],
                    "correct": 1,
                    "explanation": "Октябрьская революция произошла в октябре 1917 года по старому стилю."
                },
                {
                    "question": "Кто был первым императором Римской империи?",
                    "options": ["Юлий Цезарь", "Октавиан Август", "Марк Антоний", "Помпей"],
                    "correct": 1,
                    "explanation": "Октавиан Август стал первым римским императором в 27 году до н.э."
                }
            ],
            "hard": [
                {
                    "question": "Кто был последним императором Западной Римской империи?",
                    "options": ["Ромул Августул", "Юлий Непот", "Одоакр", "Теодорих"],
                    "correct": 0,
                    "explanation": "Ромул Августул был последним императором Западной Римской империи (476 г.)."
                },
                {
                    "question": "В каком году состоялась битва при Каннах?",
                    "options": ["218 до н.э.", "216 до н.э.", "214 до н.э.", "212 до н.э."],
                    "correct": 1,
                    "explanation": "Битва при Каннах между Римом и Карфагеном произошла 2 августа 216 года до н.э."
                }
            ]
        },
        "science": {
            "easy": [
                {
                    "question": "Какой элемент имеет химический символ 'O'?",
                    "options": ["Олово", "Кислород", "Золото", "Осмий"],
                    "correct": 1,
                    "explanation": "Кислород обозначается символом O в периодической таблице."
                },
                {
                    "question": "Сколько планет в Солнечной системе?",
                    "options": ["7", "8", "9", "10"],
                    "correct": 1,
                    "explanation": "В Солнечной системе 8 планет после исключения Плутона из их числа в 2006 году."
                },
                {
                    "question": "Что изучает ботаника?",
                    "options": ["Животных", "Растения", "Минералы", "Звезды"],
                    "correct": 1,
                    "explanation": "Ботаника - наука о растениях."
                },
                {
                    "question": "Сколько хромосом у человека?",
                    "options": ["44", "46", "48", "50"],
                    "correct": 1,
                    "explanation": "У человека 46 хромосом (23 пары)."
                },
                {
                    "question": "Какая планета ближайшая к Солнцу?",
                    "options": ["Венера", "Земля", "Меркурий", "Марс"],
                    "correct": 2,
                    "explanation": "Меркурий - ближайшая к Солнцу планета."
                }
            ],
            "medium": [
                {
                    "question": "Какой газ составляет большую часть атмосферы Земли?",
                    "options": ["Кислород", "Азот", "Углекислый газ", "Аргон"],
                    "correct": 1,
                    "explanation": "Азот составляет около 78% атмосферы Земли."
                },
                {
                    "question": "Кто создал теорию относительности?",
                    "options": ["Ньютон", "Эйнштейн", "Галилей", "Кеплер"],
                    "correct": 1,
                    "explanation": "Альберт Эйнштейн создал специальную и общую теории относительности."
                },
                {
                    "question": "Какая скорость света в вакууме (приблизительно)?",
                    "options": ["300,000 км/с", "150,000 км/с", "450,000 км/с", "500,000 км/с"],
                    "correct": 0,
                    "explanation": "Скорость света в вакууме составляет примерно 300,000 км/с."
                }
            ],
            "hard": [
                {
                    "question": "Какая частица является переносчиком слабого ядерного взаимодействия?",
                    "options": ["Фотон", "Глюон", "W и Z бозоны", "Гравитон"],
                    "correct": 2,
                    "explanation": "W и Z бозоны являются переносчиками слабого ядерного взаимодействия."
                },
                {
                    "question": "Что такое энтропия в термодинамике?",
                    "options": ["Мера энергии", "Мера беспорядка", "Мера температуры", "Мера давления"],
                    "correct": 1,
                    "explanation": "Энтропия - это мера беспорядка или хаотичности системы."
                }
            ]
        },
        "geography": {
            "easy": [
                {
                    "question": "Столица Японии?",
                    "options": ["Осака", "Киото", "Токио", "Нагоя"],
                    "correct": 2,
                    "explanation": "Токио является столицей Японии с 1868 года."
                },
                {
                    "question": "Самый большой океан на Земле?",
                    "options": ["Атлантический", "Индийский", "Северный Ледовитый", "Тихий"],
                    "correct": 3,
                    "explanation": "Тихий океан - самый большой океан, покрывающий треть поверхности Земли."
                },
                {
                    "question": "Сколько континентов на Земле?",
                    "options": ["5", "6", "7", "8"],
                    "correct": 2,
                    "explanation": "На Земле 7 континентов: Азия, Африка, Европа, Северная и Южная Америка, Австралия и Антарктида."
                },
                {
                    "question": "Самая высокая гора в мире?",
                    "options": ["К2", "Эверест", "Канченджанга", "Лхоцзе"],
                    "correct": 1,
                    "explanation": "Эверест (Джомолунгма) - самая высокая гора в мире (8849 м)."
                }
            ],
            "medium": [
                {
                    "question": "Какая река самая длинная в мире?",
                    "options": ["Амазонка", "Нил", "Миссисипи", "Янцзы"],
                    "correct": 1,
                    "explanation": "Нил - самая длинная река в мире (6650 км)."
                },
                {
                    "question": "В какой стране находится Мачу-Пикчу?",
                    "options": ["Бразилия", "Перу", "Чили", "Аргентина"],
                    "correct": 1,
                    "explanation": "Мачу-Пикчу - древний город инков, расположенный в Перу."
                },
                {
                    "question": "Столица Австралии?",
                    "options": ["Сидней", "Мельбурн", "Канберра", "Брисбен"],
                    "correct": 2,
                    "explanation": "Канберра является столицей Австралии с 1913 года."
                }
            ],
            "hard": [
                {
                    "question": "В какой стране находится пустыня Атакама?",
                    "options": ["Перу", "Чили", "Аргентина", "Боливия"],
                    "correct": 1,
                    "explanation": "Пустыня Атакама расположена в северной части Чили."
                },
                {
                    "question": "Какой пролив разделяет Европу и Азию в районе Стамбула?",
                    "options": ["Дарданеллы", "Босфор", "Гибралтарский", "Ла-Манш"],
                    "correct": 1,
                    "explanation": "Пролив Босфор разделяет европейскую и азиатскую части Турции."
                }
            ]
        },
        "sports": {
            "easy": [
                {
                    "question": "Сколько игроков в футбольной команде на поле?",
                    "options": ["10", "11", "12", "9"],
                    "correct": 1,
                    "explanation": "В футболе на поле одновременно играют 11 игроков от каждой команды."
                },
                {
                    "question": "В каком виде спорта используется шайба?",
                    "options": ["Футбол", "Баскетбол", "Хоккей", "Теннис"],
                    "correct": 2,
                    "explanation": "В хоккее используется шайба вместо мяча."
                },
                {
                    "question": "Сколько очков дается за трехочковый бросок в баскетболе?",
                    "options": ["2", "3", "4", "5"],
                    "correct": 1,
                    "explanation": "За трехочковый бросок в баскетболе дается 3 очка."
                },
                {
                    "question": "В каком виде спорта используется ракетка и волан?",
                    "options": ["Теннис", "Бадминтон", "Сквош", "Пинг-понг"],
                    "correct": 1,
                    "explanation": "В бадминтоне используется ракетка и волан (шаттлкок)."
                }
            ],
            "medium": [
                {
                    "question": "Как часто проводятся летние Олимпийские игры?",
                    "options": ["Каждые 2 года", "Каждые 3 года", "Каждые 4 года", "Каждые 5 лет"],
                    "correct": 2,
                    "explanation": "Летние Олимпийские игры проводятся каждые 4 года."
                },
                {
                    "question": "В каком году состоялись первые современные Олимпийские игры?",
                    "options": ["1892", "1896", "1900", "1904"],
                    "correct": 1,
                    "explanation": "Первые современные Олимпийские игры состоялись в Афинах в 1896 году."
                }
            ],
            "hard": [
                {
                    "question": "Кто установил мировой рекорд в беге на 100 метров среди мужчин?",
                    "options": ["Усэйн Болт", "Карл Льюис", "Морис Грин", "Тайсон Гэй"],
                    "correct": 0,
                    "explanation": "Усэйн Болт установил мировой рекорд в беге на 100м - 9.58 секунды (2009)."
                }
            ]
        },
        "technology": {
            "easy": [
                {
                    "question": "Что означает 'WWW'?",
                    "options": ["World Wide Web", "World War Web", "Wide World Web", "World Web Wide"],
                    "correct": 0,
                    "explanation": "WWW расшифровывается как World Wide Web - всемирная паутина."
                },
                {
                    "question": "Кто основал компанию Apple?",
                    "options": ["Билл Гейтс", "Стив Джобс", "Марк Цукерберг", "Илон Маск"],
                    "correct": 1,
                    "explanation": "Стив Джобс основал Apple в 1976 году вместе со Стивом Возняком."
                },
                {
                    "question": "Какая компания разработала операционную систему Windows?",
                    "options": ["Apple", "Google", "Microsoft", "IBM"],
                    "correct": 2,
                    "explanation": "Операционную систему Windows разработала компания Microsoft."
                }
            ],
            "medium": [
                {
                    "question": "В каком году был создан первый iPhone?",
                    "options": ["2005", "2006", "2007", "2008"],
                    "correct": 2,
                    "explanation": "Первый iPhone был представлен Apple в 2007 году."
                },
                {
                    "question": "Что означает аббревиатура 'HTTP'?",
                    "options": ["HyperText Transfer Protocol", "High Tech Transfer Protocol", "HyperText Transport Protocol", "High Text Transfer Protocol"],
                    "correct": 0,
                    "explanation": "HTTP расшифровывается как HyperText Transfer Protocol."
                }
            ],
            "hard": [
                {
                    "question": "Какой язык программирования был создан Гвидо ван Россумом?",
                    "options": ["Java", "Python", "C++", "JavaScript"],
                    "correct": 1,
                    "explanation": "Python был создан Гвидо ван Россумом в начале 1990-х годов."
                },
                {
                    "question": "В каком году был изобретен транзистор?",
                    "options": ["1947", "1948", "1949", "1950"],
                    "correct": 0,
                    "explanation": "Транзистор был изобретен в Bell Labs в 1947 году."
                }
            ]
        },
        "arts": {
            "easy": [
                {
                    "question": "Кто написал картину 'Мона Лиза'?",
                    "options": ["Микеланджело", "Леонардо да Винчи", "Рафаэль", "Донателло"],
                    "correct": 1,
                    "explanation": "Мону Лизу написал Леонардо да Винчи между 1503-1519 годами."
                },
                {
                    "question": "Кто написал роман 'Гарри Поттер'?",
                    "options": ["Дж. Р. Р. Толкин", "Дж. К. Роулинг", "Стивен Кинг", "Джордж Мартин"],
                    "correct": 1,
                    "explanation": "Серию книг о Гарри Поттере написала Дж. К. Роулинг."
                },
                {
                    "question": "Кто написал 'Войну и мир'?",
                    "options": ["Достоевский", "Толстой", "Пушкин", "Тургенев"],
                    "correct": 1,
                    "explanation": "Лев Толстой написал роман 'Война и мир' (1865-1869)."
                }
            ],
            "medium": [
                {
                    "question": "В каком музее находится картина 'Звездная ночь' Ван Гога?",
                    "options": ["Лувр", "Эрмитаж", "Музей современного искусства (MoMA)", "Прадо"],
                    "correct": 2,
                    "explanation": "'Звездная ночь' находится в Музее современного искусства в Нью-Йорке."
                },
                {
                    "question": "Кто написал симфонию 'К Элизе'?",
                    "options": ["Моцарт", "Бетховен", "Бах", "Шопен"],
                    "correct": 1,
                    "explanation": "'К Элизе' - знаменитая пьеса Людвига ван Бетховена."
                }
            ],
            "hard": [
                {
                    "question": "Кто композитор оперы 'Кармен'?",
                    "options": ["Моцарт", "Бизе", "Верди", "Пуччини"],
                    "correct": 1,
                    "explanation": "Оперу 'Кармен' написал французский композитор Жорж Бизе."
                }
            ]
        }
    }
    
    try:
        with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(questions, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ Создан файл вопросов: {QUESTIONS_FILE}")
    except Exception as e:
        logger.error(f"❌ Ошибка создания файла вопросов: {e}")
        raise

def load_questions():
    """Загрузка вопросов из файла"""
    try:
        if not os.path.exists(QUESTIONS_FILE):
            logger.info("📄 Файл вопросов не найден, создаем новый...")
            create_questions_file()
        
        with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Подсчет общего количества вопросов
        total_questions = sum(
            len(difficulties.get(diff, [])) 
            for category, difficulties in data.items()
            for diff in ['easy', 'medium', 'hard']
        )
        
        logger.info(f"✅ Загружено {len(data)} категорий, {total_questions} вопросов")
        return data
        
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки вопросов: {e}")
        return {}

# =====================================
# БИЗНЕС-ЛОГИКА
# =====================================

def create_or_update_user_profile(user_data):
    """Создание или обновление профиля пользователя"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        user_id = user_data.get('user_id')
        if not user_id:
            raise ValueError("User ID is required")
        
        # Проверяем существование профиля
        existing = cursor.execute(
            'SELECT user_id FROM user_profiles WHERE user_id = ?', 
            (user_id,)
        ).fetchone()
        
        if existing:
            # Обновляем существующий профиль
            cursor.execute('''
                UPDATE user_profiles 
                SET username = ?, first_name = ?, last_name = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (
                user_data.get('username', ''),
                user_data.get('first_name', 'Игрок'),
                user_data.get('last_name', ''),
                user_id
            ))
            logger.debug(f"Updated profile for user {user_id}")
        else:
            # Создаем новый профиль
            cursor.execute('''
                INSERT INTO user_profiles 
                (user_id, username, first_name, last_name, total_games, total_score, 
                 best_streak, current_streak, achievements, level, experience_points)
                VALUES (?, ?, ?, ?, 0, 0, 0, 0, '[]', 1, 0)
            ''', (
                user_id,
                user_data.get('username', ''),
                user_data.get('first_name', 'Игрок'),
                user_data.get('last_name', '')
            ))
            logger.info(f"Created new profile for user {user_id}")
        
        db.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error creating/updating user profile: {e}")
        return False

def check_achievements(user_id, game_result):
    """Проверка и присвоение достижений"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Получаем текущие достижения пользователя
        profile = cursor.execute(
            'SELECT achievements, total_games FROM user_profiles WHERE user_id = ?',
            (user_id,)
        ).fetchone()
        
        if not profile:
            return []
        
        current_achievements = json.loads(profile['achievements'] or '[]')
        new_achievements = []
        
        # Получаем все достижения
        all_achievements = cursor.execute('SELECT * FROM achievements').fetchall()
        
        for achievement in all_achievements:
            if achievement['id'] in current_achievements:
                continue
                
            # Проверяем условия для достижения
            earned = False
            
            if achievement['condition_type'] == 'games_played':
                total_games = profile['total_games'] + 1  # +1 за текущую игру
                earned = total_games >= achievement['condition_value']
                
            elif achievement['condition_type'] == 'perfect_score':
                earned = game_result.get('percentage', 0) == 100
                
            elif achievement['condition_type'] == 'marathon_completed':
                earned = game_result.get('game_mode') == 'marathon'
                
            elif achievement['condition_type'] == 'speed_completion':
                earned = game_result.get('time_spent', 999) <= achievement['condition_value']
                
            elif achievement['condition_type'] == 'category_master':
                # Подсчитываем категории с 80%+ результатом
                categories_80_plus = cursor.execute('''
                    SELECT COUNT(DISTINCT category) FROM game_results 
                    WHERE user_id = ? AND percentage >= 80
                ''', (user_id,)).fetchone()[0]
                earned = categories_80_plus >= achievement['condition_value']
            
            if earned:
                current_achievements.append(achievement['id'])
                new_achievements.append({
                    'id': achievement['id'],
                    'name': achievement['name'],
                    'description': achievement['description'],
                    'icon': achievement['icon'],
                    'points': achievement['reward_points'],
                    'rarity': achievement['rarity']
                })
        
        # Обновляем достижения в профиле
        if new_achievements:
            cursor.execute('''
                UPDATE user_profiles 
                SET achievements = ?, experience_points = experience_points + ?
                WHERE user_id = ?
            ''', (
                json.dumps(current_achievements),
                sum(ach['points'] for ach in new_achievements),
                user_id
            ))
            db.commit()
        
        return new_achievements
        
    except Exception as e:
        logger.error(f"Error checking achievements: {e}")
        return []

def update_daily_challenge_progress(user_id, game_result):
    """Обновление прогресса ежедневных заданий"""
    try:
        db = get_db()
        cursor = db.cursor()
        today = date.today()
        
        # Получаем активные задания пользователя на сегодня
        challenges = cursor.execute('''
            SELECT * FROM daily_challenges 
            WHERE user_id = ? AND challenge_date = ? AND completed = FALSE
        ''', (user_id, today)).fetchall()
        
        for challenge in challenges:
            progress_made = False
            new_progress = challenge['current_progress']
            
            if challenge['challenge_type'] == 'games_count':
                new_progress += 1
                progress_made = True
                
            elif challenge['challenge_type'] == 'category_master' and game_result.get('percentage', 0) >= 80:
                new_progress = challenge['target_value']  # Выполнено сразу
                progress_made = True
                
            elif challenge['challenge_type'] == 'perfect_answers' and game_result.get('percentage', 0) == 100:
                new_progress = min(new_progress + game_result.get('total', 0), challenge['target_value'])
                progress_made = True
            
            if progress_made:
                completed = new_progress >= challenge['target_value']
                cursor.execute('''
                    UPDATE daily_challenges 
                    SET current_progress = ?, completed = ?
                    WHERE id = ?
                ''', (new_progress, completed, challenge['id']))
        
        db.commit()
        
    except Exception as e:
        logger.error(f"Error updating daily challenges: {e}")

def create_daily_challenge(user_id):
    """Создание ежедневного задания для пользователя"""
    try:
        db = get_db()
        cursor = db.cursor()
        today = date.today()
        
        # Проверяем, есть ли уже задание на сегодня
        existing = cursor.execute('''
            SELECT id FROM daily_challenges 
            WHERE user_id = ? AND challenge_date = ?
        ''', (user_id, today)).fetchone()
        
        if existing:
            return
        
        # Создаем случайное задание
        challenges = [
            {
                'type': 'games_count',
                'target': 3,
                'description': 'Сыграйте 3 игры сегодня'
            },
            {
                'type': 'category_master',
                'target': 80,
                'description': 'Наберите 80%+ в любой категории'
            },
            {
                'type': 'perfect_answers',
                'target': 5,
                'description': 'Ответьте правильно на 5 вопросов'
            }
        ]
        
        challenge = random.choice(challenges)
        
        cursor.execute('''
            INSERT INTO daily_challenges 
            (user_id, challenge_date, challenge_type, target_value)
            VALUES (?, ?, ?, ?)
        ''', (user_id, today, challenge['type'], challenge['target']))
        
        db.commit()
        logger.debug(f"Created daily challenge for user {user_id}")
        
    except Exception as e:
        logger.error(f"Error creating daily challenge: {e}")

# =====================================
# МАРШРУТЫ API
# =====================================

@app.before_request
def before_request():
    """Предобработка запросов"""
    # Логирование запросов
    if not request.path.startswith('/static/'):
        logger.debug(f"🌐 {request.method} {request.path} - {request.remote_addr}")

@app.after_request
def after_request(response):
    """Постобработка ответов"""
    # Добавляем CORS заголовки
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    
    # Логирование ответов
    if not request.path.startswith('/static/'):
        logger.debug(f"📤 {response.status_code} - {response.content_length or 0} bytes")
    
    return response

@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')

@app.route('/api/questions/<category>/<difficulty>')
@handle_db_error
def get_questions(category, difficulty):
    """API для получения вопросов"""
    questions_data = load_questions()
    
    if category not in questions_data:
        logger.warning(f"Category {category} not found")
        return jsonify({'error': f'Category {category} not found'}), 404
        
    if difficulty not in questions_data[category]:
        logger.warning(f"Difficulty {difficulty} not found in category {category}")
        return jsonify({'error': f'Difficulty {difficulty} not found'}), 404
    
    category_questions = questions_data[category][difficulty].copy()
    random.shuffle(category_questions)
    
    logger.info(f"📚 Sent {len(category_questions)} questions for {category}/{difficulty}")
    return jsonify(category_questions)

@app.route('/api/profile/<user_id>')
@handle_db_error
def get_profile(user_id):
    """Получение профиля пользователя"""
    db = get_db()
    cursor = db.cursor()
    
    # Получаем или создаем профиль
    profile = cursor.execute(
        'SELECT * FROM user_profiles WHERE user_id = ?', 
        (user_id,)
    ).fetchone()
    
    if not profile:
        # Создаем базовый профиль
        create_or_update_user_profile({
            'user_id': user_id,
            'first_name': 'Игрок',
            'username': '',
            'last_name': ''
        })
        profile = cursor.execute(
            'SELECT * FROM user_profiles WHERE user_id = ?', 
            (user_id,)
        ).fetchone()
    
    # Статистика по категориям
    category_stats = cursor.execute('''
        SELECT category, COUNT(*) as games, 
               AVG(percentage) as avg_score, MAX(percentage) as best_score
        FROM game_results 
        WHERE user_id = ? 
        GROUP BY category
    ''', (user_id,)).fetchall()
    
    # Последние игры
    recent_games = cursor.execute('''
        SELECT category, difficulty, score, total, percentage, created_at
        FROM game_results 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT 10
    ''', (user_id,)).fetchall()
    
    # Достижения
    all_achievements = cursor.execute('SELECT * FROM achievements ORDER BY rarity, name').fetchall()
    user_achievements = json.loads(profile['achievements'] or '[]')
    
    return jsonify({
        'profile': {
            'user_id': profile['user_id'],
            'username': profile['username'] or '',
            'first_name': profile['first_name'],
            'last_name': profile['last_name'] or '',
            'total_games': profile['total_games'],
            'total_score': profile['total_score'],
            'best_streak': profile['best_streak'],
            'current_streak': profile['current_streak'],
            'level': profile['level'],
            'experience_points': profile['experience_points'],
            'created_at': profile['created_at'],
            'updated_at': profile['updated_at']
        },
        'category_stats': [
            {
                'category': stat['category'],
                'games': stat['games'],
                'avg_score': round(stat['avg_score'] or 0, 1),
                'best_score': round(stat['best_score'] or 0, 1)
            } for stat in category_stats
        ],
        'recent_games': [
            {
                'category': game['category'],
                'difficulty': game['difficulty'],
                'score': f"{game['score']}/{game['total']}",
                'percentage': round(game['percentage'], 1),
                'date': game['created_at']
            } for game in recent_games
        ],
        'achievements': [
            {
                'id': ach['id'],
                'name': ach['name'],
                'description': ach['description'],
                'icon': ach['icon'],
                'rarity': ach['rarity'],
                'reward_points': ach['reward_points'],
                'unlocked': ach['id'] in user_achievements
            } for ach in all_achievements
        ]
    })

@app.route('/api/save_game', methods=['POST'])
@handle_db_error
def save_game():
    """Сохранение результата игры"""
    data = request.get_json()
    
    if not data or 'user_id' not in data:
        return jsonify({'error': 'Invalid data'}), 400
    
    # Создаем/обновляем профиль пользователя
    create_or_update_user_profile(data)
    
    # Сохраняем результат игры
    db = get_db()
    cursor = db.cursor()
    
    percentage = (data.get('score', 0) / max(data.get('total', 1), 1)) * 100
    
    cursor.execute('''
        INSERT INTO game_results 
        (user_id, username, first_name, last_name, score, total, category, 
         difficulty, percentage, time_spent, hints_used, game_mode)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data.get('user_id'),
        data.get('username', ''),
        data.get('first_name', 'Игрок'),
        data.get('last_name', ''),
        data.get('score', 0),
        data.get('total', 0),
        data.get('category', 'unknown'),
        data.get('difficulty', 'easy'),
        percentage,
        data.get('time_spent', 0),
        data.get('hints_used', 0),
        data.get('game_mode', 'normal')
    ))
    
    # Обновляем статистику профиля
    cursor.execute('''
        UPDATE user_profiles 
        SET total_games = total_games + 1,
            total_score = total_score + ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
    ''', (data.get('score', 0), data.get('user_id')))
    
    db.commit()
    
    # Проверяем достижения
    game_result = {
        'percentage': percentage,
        'game_mode': data.get('game_mode', 'normal'),
        'time_spent': data.get('time_spent', 0),
        'total': data.get('total', 0)
    }
    
    new_achievements = check_achievements(data.get('user_id'), game_result)
    
    # Обновляем ежедневные задания
    update_daily_challenge_progress(data.get('user_id'), game_result)
    
    logger.info(f"💾 Game saved for user {data.get('user_id')}: {data.get('score')}/{data.get('total')} ({percentage:.1f}%)")
    
    return jsonify({
        'status': 'success',
        'new_achievements': new_achievements
    })

@app.route('/api/leaderboard/<category>')
@handle_db_error
def get_leaderboard(category):
    """Таблица лидеров по категории"""
    db = get_db()
    cursor = db.cursor()
    
    if category == 'overall':
        results = cursor.execute('''
            SELECT user_id, username, first_name, COUNT(*) as games, 
                   AVG(percentage) as avg_score, MAX(percentage) as best_score
            FROM game_results 
            GROUP BY user_id 
            HAVING games >= 3
            ORDER BY avg_score DESC, best_score DESC 
            LIMIT 100
        ''').fetchall()
    else:
        results = cursor.execute('''
            SELECT user_id, username, first_name, COUNT(*) as games,
                   AVG(percentage) as avg_score, MAX(percentage) as best_score
            FROM game_results 
            WHERE category = ?
            GROUP BY user_id 
            HAVING games >= 2
            ORDER BY avg_score DESC, best_score DESC 
            LIMIT 100
        ''', (category,)).fetchall()
    
    leaderboard = []
    for row in results:
        leaderboard.append({
            'user_id': row['user_id'],
            'username': row['username'] or '',
            'first_name': row['first_name'] or 'Игрок',
            'games': row['games'],
            'avg_score': round(row['avg_score'] or 0, 1),
            'best_score': round(row['best_score'] or 0, 1)
        })
    
    logger.info(f"🏆 Leaderboard for {category}: {len(leaderboard)} entries")
    return jsonify(leaderboard)

@app.route('/api/daily_challenge/<user_id>')
@handle_db_error
def get_daily_challenge(user_id):
    """Получение ежедневного задания"""
    db = get_db()
    cursor = db.cursor()
    today = date.today()
    
    # Создаем задание, если его нет
    create_daily_challenge(user_id)
    
    # Получаем задание на сегодня
    challenge = cursor.execute('''
        SELECT * FROM daily_challenges 
        WHERE user_id = ? AND challenge_date = ?
        ORDER BY id DESC
        LIMIT 1
    ''', (user_id, today)).fetchone()
    
    if not challenge:
        # Создаем базовое задание
        return jsonify({
            'type': 'games_count',
            'description': 'Сыграйте первую игру сегодня!',
            'target': 1,
            'progress': 0,
            'completed': False
        })
    
    # Описание задания
    descriptions = {
        'games_count': f'Сыграйте {challenge["target_value"]} игр сегодня',
        'category_master': 'Наберите 80%+ в любой категории',
        'perfect_answers': f'Ответьте правильно на {challenge["target_value"]} вопросов'
    }
    
    return jsonify({
        'type': challenge['challenge_type'],
        'description': descriptions.get(challenge['challenge_type'], 'Ежедневное задание'),
        'target': challenge['target_value'],
        'progress': challenge['current_progress'],
        'completed': bool(challenge['completed'])
    })

@app.route('/api/stats')
@handle_db_error
def get_app_stats():
    """Общая статистика приложения"""
    db = get_db()
    cursor = db.cursor()
    
    # Общая статистика
    total_users = cursor.execute('SELECT COUNT(DISTINCT user_id) FROM user_profiles').fetchone()[0]
    total_games = cursor.execute('SELECT COUNT(*) FROM game_results').fetchone()[0]
    total_questions = cursor.execute('SELECT SUM(total) FROM game_results').fetchone()[0] or 0
    
    # Статистика по категориям
    category_stats = cursor.execute('''
        SELECT category, COUNT(*) as games, AVG(percentage) as avg_score
        FROM game_results 
        GROUP BY category
        ORDER BY games DESC
    ''').fetchall()
    
    return jsonify({
        'total_users': total_users,
        'total_games': total_games,
        'total_questions_answered': total_questions,
        'category_stats': [
            {
                'category': stat['category'],
                'games': stat['games'],
                'avg_score': round(stat['avg_score'] or 0, 1)
            } for stat in category_stats
        ]
    })

# =====================================
# АДМИНИСТРАТИВНЫЕ МАРШРУТЫ
# =====================================

@app.route('/health')
def health():
    """Проверка здоровья приложения"""
    try:
        # Проверка базы данных
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT COUNT(*) FROM user_profiles')
        users_count = cursor.fetchone()[0]
        
        # Проверка файла вопросов
        questions_data = load_questions()
        questions_count = sum(
            len(difficulties.get(diff, [])) 
            for category, difficulties in questions_data.items()
            for diff in ['easy', 'medium', 'hard']
        )
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': {
                'connected': True,
                'users_count': users_count
            },
            'questions': {
                'loaded': questions_count,
                'categories': len(questions_data)
            },
            'version': '2.0.0'
        })
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/debug/questions')
def debug_questions():
    """Отладочная информация о вопросах"""
    if not DEBUG:
        return jsonify({'error': 'Debug mode disabled'}), 403
    
    questions = load_questions()
    result = {}
    total = 0
    
    for category, difficulties in questions.items():
        result[category] = {}
        for difficulty, question_list in difficulties.items():
            count = len(question_list)
            result[category][difficulty] = count
            total += count
    
    result['total'] = total
    return jsonify(result)

@app.route('/debug/database')
def debug_database():
    """Отладочная информация о базе данных"""
    if not DEBUG:
        return jsonify({'error': 'Debug mode disabled'}), 403
    
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Получаем информацию о таблицах
        tables = cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """).fetchall()
        
        table_info = {}
        for table in tables:
            table_name = table[0]
            count = cursor.execute(f'SELECT COUNT(*) FROM {table_name}').fetchone()[0]
            table_info[table_name] = count
        
        return jsonify({
            'tables': table_info,
            'database_path': DATABASE_PATH
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =====================================
# ОБРАБОТЧИКИ ОШИБОК
# =====================================

@app.errorhandler(404)
def not_found(error):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Not found'}), 404
    return render_template('index.html')  # SPA fallback

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    return render_template('index.html')

@app.errorhandler(400)
def bad_request(error):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Bad request'}), 400
    return render_template('index.html')

# =====================================
# ИНИЦИАЛИЗАЦИЯ И ЗАПУСК
# =====================================

def initialize_app():
    """Полная инициализация приложения"""
    try:
        logger.info("🚀 Инициализация Enhanced Quiz Mini App...")
        
        # Инициализация базы данных
        init_database()
        
        # Инициализация достижений
        init_achievements()
        
        # Проверка файла вопросов
        questions = load_questions()
        if not questions:
            logger.warning("⚠️ Вопросы не загружены")
        
        logger.info("✅ Инициализация завершена успешно")
        return True
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка инициализации: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == '__main__':
    # Инициализация приложения
    if not initialize_app():
        logger.error("❌ Не удалось инициализировать приложение")
        exit(1)
    
    # Запуск сервера
    port = int(os.environ.get('PORT', 5000))
    host = '0.0.0.0' if not DEBUG else 'localhost'
    
    logger.info(f"🌐 Запуск сервера на {host}:{port}")
    logger.info(f"🔧 Режим отладки: {DEBUG}")
    
    app.run(
        host=host, 
        port=port, 
        debug=DEBUG,
        threaded=True
    )
