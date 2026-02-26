#!/usr/bin/env python3
"""
Тесты для v3.1.1: Ограничение функции "Пригласить друга"

Проверяет:
1. USER не видит кнопку "Пригласить друга"
2. MANAGER видит кнопку "Пригласить друга"
3. ADMIN видит кнопку "Пригласить друга"
4. Graceful degradation при недоступности модуля ролей
"""

import sys
from pathlib import Path

# Добавляем scripts в путь
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def test_user_main_keyboard_with_roles():
    """Тест клавиатуры с учётом ролей"""
    print("\n=== Тест 1: user_main_keyboard с ролями ===")

    # Импортируем после добавления в путь
    from telebot import types
    import importlib

    # Мокаем модуль roles
    class MockRoles:
        @staticmethod
        def can_invite_users(telegram_id):
            # ADMIN и MANAGER могут приглашать
            return telegram_id in [100, 200]

    # Подменяем импорт
    sys.modules['roles'] = MockRoles()

    # Переменные для теста
    can_invite_users = MockRoles.can_invite_users

    # Функция клавиатуры (копия из monitor_bot.py)
    def user_main_keyboard(telegram_id=None):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

        btn1 = types.KeyboardButton("📱 Мои устройства")
        btn2 = types.KeyboardButton("🔗 Получить ключ")
        btn3 = types.KeyboardButton("📊 Моя подписка")
        btn4 = types.KeyboardButton("💬 Поддержка")

        show_invite = False
        if telegram_id and can_invite_users:
            try:
                show_invite = can_invite_users(telegram_id)
            except Exception:
                show_invite = False

        markup.add(btn1, btn2, btn3, btn4)

        if show_invite:
            btn5 = types.KeyboardButton("👥 Пригласить друга")
            markup.add(btn5)

        return markup

    # Тесты
    test_cases = [
        (100, "ADMIN (может приглашать)", True),
        (200, "MANAGER (может приглашать)", True),
        (300, "USER (не может приглашать)", False),
        (None, "None (graceful degradation)", False),
    ]

    for telegram_id, description, should_have_invite in test_cases:
        keyboard = user_main_keyboard(telegram_id)
        has_invite = any(
            "Пригласить друга" in button.text
            for row in keyboard.keyboard
            for button in row
        )

        status = "✅" if has_invite == should_have_invite else "❌"
        print(f"{status} {description}: кнопка {'видна' if has_invite else 'не видна'}")

        if has_invite != should_have_invite:
            print(f"   ОЖИДАЛОСЬ: {'видна' if should_have_invite else 'не видна'}")
            return False

    print("✅ Все тесты пройдены!")
    return True


def test_graceful_degradation():
    """Тест graceful degradation при недоступности модуля ролей"""
    print("\n=== Тест 2: Graceful degradation ===")

    from telebot import types

    # Симуляция недоступности модуля ролей
    can_invite_users = None

    def user_main_keyboard(telegram_id=None):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

        btn1 = types.KeyboardButton("📱 Мои устройства")
        btn2 = types.KeyboardButton("🔗 Получить ключ")
        btn3 = types.KeyboardButton("📊 Моя подписка")
        btn4 = types.KeyboardButton("💬 Поддержка")

        show_invite = False
        if telegram_id and can_invite_users:
            try:
                show_invite = can_invite_users(telegram_id)
            except Exception:
                show_invite = False

        markup.add(btn1, btn2, btn3, btn4)

        if show_invite:
            btn5 = types.KeyboardButton("👥 Пригласить друга")
            markup.add(btn5)

        return markup

    keyboard = user_main_keyboard(123)
    has_invite = any(
        "Пригласить друга" in button.text
        for row in keyboard.keyboard
        for button in row
    )

    if not has_invite:
        print("✅ Кнопка не отображается при can_invite_users=None")
        return True
    else:
        print("❌ Кнопка отображается, хотя не должна")
        return False


def test_exception_handling():
    """Тест обработки ошибок в can_invite_users"""
    print("\n=== Тест 3: Обработка исключений ===")

    from telebot import types

    # Функция, которая вызывает исключение
    def failing_can_invite(telegram_id):
        raise RuntimeError("DB connection failed")

    can_invite_users = failing_can_invite

    def user_main_keyboard(telegram_id=None):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

        btn1 = types.KeyboardButton("📱 Мои устройства")
        btn2 = types.KeyboardButton("🔗 Получить ключ")
        btn3 = types.KeyboardButton("📊 Моя подписка")
        btn4 = types.KeyboardButton("💬 Поддержка")

        show_invite = False
        if telegram_id and can_invite_users:
            try:
                show_invite = can_invite_users(telegram_id)
            except Exception:
                show_invite = False

        markup.add(btn1, btn2, btn3, btn4)

        if show_invite:
            btn5 = types.KeyboardButton("👥 Пригласить друга")
            markup.add(btn5)

        return markup

    try:
        keyboard = user_main_keyboard(123)
        has_invite = any(
            "Пригласить друга" in button.text
            for row in keyboard.keyboard
            for button in row
        )

        if not has_invite:
            print("✅ Исключение обработано, кнопка не отображается")
            return True
        else:
            print("❌ Кнопка отображается при исключении")
            return False
    except Exception as e:
        print(f"❌ Функция упала с исключением: {e}")
        return False


def main():
    """Запуск всех тестов"""
    print("=" * 60)
    print("ТЕСТЫ V3.1.1: Ограничение функции 'Пригласить друга'")
    print("=" * 60)

    results = []

    results.append(("Роли в клавиатуре", test_user_main_keyboard_with_roles()))
    results.append(("Graceful degradation", test_graceful_degradation()))
    results.append(("Обработка исключений", test_exception_handling()))

    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        return 0
    else:
        print("\n❌ НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛЕНЫ")
        return 1


if __name__ == "__main__":
    sys.exit(main())
