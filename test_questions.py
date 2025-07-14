#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для тестирования файла вопросов
"""

import json
import os
import sys

def test_questions_file():
    """Тестирование файла вопросов"""
    
    print("=== ТЕСТ ФАЙЛА ВОПРОСОВ ===")
    
    # Проверяем существование файла
    if not os.path.exists('questions.json'):
        print("❌ Файл questions.json не найден")
        return False
    
    print("✅ Файл questions.json найден")
    print(f"📦 Размер файла: {os.path.getsize('questions.json')} байт")
    
    try:
        # Загружаем файл
        with open('questions.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print("✅ Файл успешно загружен как JSON")
        
        # Проверяем структуру
        if not isinstance(data, dict):
            print("❌ Данные не являются словарем")
            return False
        
        print(f"📚 Найдено категорий: {len(data)}")
        
        total_questions = 0
        
        for category, difficulties in data.items():
            print(f"\n📖 Категория: {category}")
            
            if not isinstance(difficulties, dict):
                print(f"❌ Сложности для {category} не являются словарем")
                continue
            
            for difficulty, questions in difficulties.items():
                if not isinstance(questions, list):
                    print(f"❌ Вопросы для {category}/{difficulty} не являются списком")
                    continue
                
                question_count = len(questions)
                total_questions += question_count
                print(f"   🎯 {difficulty}: {question_count} вопросов")
                
                # Проверяем первый вопрос
                if questions:
                    first_q = questions[0]
                    required_keys = ['question', 'options', 'correct']
                    missing_keys = [key for key in required_keys if key not in first_q]
                    
                    if missing_keys:
                        print(f"❌ В первом вопросе отсутствуют ключи: {missing_keys}")
                    else:
                        print(f"   ✅ Структура вопросов корректна")
        
        print(f"\n📊 ИТОГО: {total_questions} вопросов")
        
        if total_questions > 0:
            print("✅ Файл вопросов готов к использованию!")
            return True
        else:
            print("❌ Файл не содержит вопросов")
            return False
            
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка парсинга JSON: {e}")
        return False
    
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False

def create_sample_questions():
    """Создание примера файла вопросов"""
    print("\n=== СОЗДАНИЕ ПРИМЕРА ФАЙЛА ===")
    
    sample_data = {
        "test_category": {
            "easy": [
                {
                    "question": "Тестовый вопрос?",
                    "options": ["Вариант 1", "Вариант 2", "Вариант 3", "Вариант 4"],
                    "correct": 0,
                    "explanation": "Это тестовое объяснение"
                }
            ]
        }
    }
    
    try:
        with open('questions_test.json', 'w', encoding='utf-8') as f:
            json.dump(sample_data, f, ensure_ascii=False, indent=2)
        
        print("✅ Тестовый файл questions_test.json создан")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка создания тестового файла: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--create-sample":
        create_sample_questions()
    else:
        test_questions_file()
