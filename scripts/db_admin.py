#!/usr/bin/env python3
"""
Утилита управления БД Hiddify Telegram Bot
Использование: python3 scripts/db_admin.py <команда> [аргументы]
"""

import os
import sys
import sqlite3
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), '../data/bot.db')


def connect_db():
    """Подключение к БД"""

    if not os.path.exists(DB_PATH):
        print(f"❌ БД не найдена: {DB_PATH}")
        sys.exit(1)

    return sqlite3.connect(DB_PATH)


def list_users():
    """Список всех пользователей"""

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, telegram_id, telegram_username, telegram_first_name,
               user_type, is_active, is_blocked, expires_at, used_bytes
        FROM users
        ORDER BY created_at DESC
    ''')

    users = cursor.fetchall()

    if not users:
        print("📭 Пользователей нет")
        return

    print(f"\n👥 Пользователей: {len(users)}\n")

    for user in users:
        (user_id, telegram_id, username, first_name, user_type,
         is_active, is_blocked, expires_at, used_bytes) = user

        status = "✅" if is_active and not is_blocked else "⛔"
        used_gb = used_bytes / (1024**3)

        print(f"{status} ID:{user_id} | @{username} ({first_name})")
        print(f"   Telegram ID: {telegram_id}")
        print(f"   Тип: {user_type} | Трафик: {used_gb:.2f} GB")

        if expires_at:
            expire_date = datetime.fromisoformat(expires_at)
            days_left = (expire_date - datetime.now()).days
            print(f"   Истекает: {expire_date.strftime('%d.%m.%Y')} ({days_left} дн)")

        print()

    conn.close()


def show_stats():
    """Статистика БД"""

    conn = connect_db()
    cursor = conn.cursor()

    # Общее количество
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM users WHERE is_active = 1 AND is_blocked = 0')
    active_users = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM users WHERE is_blocked = 1')
    blocked_users = cursor.fetchone()[0]

    # По типу
    cursor.execute('SELECT user_type, COUNT(*) FROM users GROUP BY user_type')
    by_type = dict(cursor.fetchall())

    # Трафик
    cursor.execute('SELECT SUM(used_bytes) FROM users')
    total_traffic = cursor.fetchone()[0] or 0
    total_traffic_gb = total_traffic / (1024**3)

    print(f"\n📊 Статистика БД\n")
    print(f"Всего пользователей: {total_users}")
    print(f"Активных: {active_users}")
    print(f"Заблокированных: {blocked_users}")
    print(f"\nПо типу:")
    for user_type, count in by_type.items():
        print(f"  {user_type}: {count}")
    print(f"\nТрафик: {total_traffic_gb:.2f} GB")
    print()

    conn.close()


def show_user(user_id):
    """Детали пользователя"""

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()

    if not user:
        print(f"❌ Пользователь ID:{user_id} не найден")
        return

    columns = [
        'id', 'telegram_id', 'telegram_username', 'telegram_first_name',
        'user_type', 'invite_code', 'invited_by', 'data_limit_bytes',
        'expire_days', 'created_at', 'expires_at', 'used_bytes',
        'last_connection', 'is_active', 'is_blocked', 'vless_enabled',
        'hysteria2_enabled', 'ss2022_enabled', 'vless_uuid',
        'hysteria2_password', 'ss2022_password'
    ]

    user_dict = dict(zip(columns, user))

    print(f"\n👤 Пользователь ID:{user_id}\n")
    print(f"Telegram: @{user_dict['telegram_username']} ({user_dict['telegram_first_name']})")
    print(f"ID: {user_dict['telegram_id']}")
    print(f"Тип: {user_dict['user_type']}")
    print(f"\nСтатус:")
    print(f"  Активен: {'✅' if user_dict['is_active'] else '❌'}")
    print(f"  Заблокирован: {'⛔' if user_dict['is_blocked'] else '✅'}")
    print(f"\nЛимиты:")
    used_gb = user_dict['used_bytes'] / (1024**3)
    limit_gb = user_dict['data_limit_bytes'] / (1024**3)
    print(f"  Трафик: {used_gb:.2f} GB / {limit_gb:.0f} GB")

    if user_dict['expires_at']:
        expire_date = datetime.fromisoformat(user_dict['expires_at'])
        days_left = (expire_date - datetime.now()).days
        print(f"  Истекает: {expire_date.strftime('%d.%m.%Y')} ({days_left} дн)")

    print(f"\nПротоколы:")
    print(f"  VLESS-Reality: {'✅' if user_dict['vless_enabled'] else '❌'}")
    print(f"  Hysteria2: {'✅' if user_dict['hysteria2_enabled'] else '❌'}")
    print(f"  SS-2022: {'✅' if user_dict['ss2022_enabled'] else '❌'}")

    print(f"\nИнвайт-код: {user_dict['invite_code']}")
    print()

    conn.close()


def extend_user(user_id, days):
    """Продлить подписку"""

    conn = connect_db()
    cursor = conn.cursor()

    # Получить текущую дату истечения
    cursor.execute('SELECT expires_at FROM users WHERE id = ?', (user_id,))
    result = cursor.fetchone()

    if not result:
        print(f"❌ Пользователь ID:{user_id} не найден")
        return

    current_expires = result[0]

    # Новая дата
    if current_expires:
        new_expires = datetime.fromisoformat(current_expires) + timedelta(days=int(days))
    else:
        new_expires = datetime.now() + timedelta(days=int(days))

    # Обновить
    cursor.execute(
        'UPDATE users SET expires_at = ? WHERE id = ?',
        (new_expires.isoformat(), user_id)
    )

    conn.commit()
    conn.close()

    print(f"✅ Подписка продлена на {days} дней")
    print(f"   Новая дата: {new_expires.strftime('%d.%m.%Y')}")


def block_user(user_id):
    """Заблокировать пользователя"""

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute('UPDATE users SET is_blocked = 1 WHERE id = ?', (user_id,))

    if cursor.rowcount == 0:
        print(f"❌ Пользователь ID:{user_id} не найден")
    else:
        print(f"⛔ Пользователь ID:{user_id} заблокирован")

    conn.commit()
    conn.close()


def unblock_user(user_id):
    """Разблокировать пользователя"""

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute('UPDATE users SET is_blocked = 0 WHERE id = ?', (user_id,))

    if cursor.rowcount == 0:
        print(f"❌ Пользователь ID:{user_id} не найден")
    else:
        print(f"✅ Пользователь ID:{user_id} разблокирован")

    conn.commit()
    conn.close()


def list_invites():
    """Список всех инвайт-кодов"""

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, code, created_by, max_uses, used_count,
               is_active, expires_at, created_at
        FROM invites
        ORDER BY created_at DESC
    ''')

    invites = cursor.fetchall()

    if not invites:
        print("📭 Инвайт-кодов нет")
        return

    print(f"\n🎫 Инвайт-кодов: {len(invites)}\n")

    for invite in invites:
        (invite_id, code, created_by, max_uses, used_count,
         is_active, expires_at, created_at) = invite

        status = "✅" if is_active else "❌"
        expires_str = ""
        if expires_at:
            expire_date = datetime.fromisoformat(expires_at)
            if expire_date > datetime.now():
                days_left = (expire_date - datetime.now()).days
                expires_str = f" (истекает через {days_left} дн)"
            else:
                expires_str = " (истёк)"

        print(f"{status} {code}")
        print(f"   ID: {invite_id} | Создан ID: {created_by}")
        print(f"   Использований: {used_count}/{max_uses}{expires_str}")
        print()

    conn.close()


def cmd_create_invite(args):
    """
    Создать инвайт-код

    Использование: create_invite [count] [days]

    Примеры:
        create_invite           # 1 инвайт, бессрочный
        create_invite 10        # 10 инвайтов, бессрочных
        create_invite 5 7       # 5 инвайтов, на 7 дней
    """

    count = int(args[0]) if len(args) > 0 else 1
    days = int(args[1]) if len(args) > 1 else None

    # Получить ID первого пользователя (админа) для created_by
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute('SELECT id FROM users ORDER BY id ASC LIMIT 1')
    result = cursor.fetchone()

    if not result:
        print("❌ В БД нет пользователей. Сначала создайте администратора через бота.")
        conn.close()
        return

    admin_id = result[0]

    invites = []
    for _ in range(count):
        code = f"INV_{os.urandom(8).hex()}"
        expires_at = None
        if days:
            expires_at = (datetime.now() + timedelta(days=days)).isoformat()

        cursor.execute('''
            INSERT INTO invites (code, created_by, max_uses, expires_at)
            VALUES (?, ?, ?, ?)
        ''', (code, admin_id, 1, expires_at))

        invites.append(code)

    conn.commit()
    conn.close()

    print(f"✅ Создано {count} инвайт-кодов:")
    for code in invites:
        expiry = f" (истекает через {days} дней)" if days else " (бессрочный)"
        print(f"  • {code}{expiry}")

    print("\nДля использования:")
    print("  https://t.me/ваш_бот?start=INV_код")


def main():
    """Главная функция"""

    if len(sys.argv) < 2:
        print("Использование:")
        print("  python3 db_admin.py list          - Список пользователей")
        print("  python3 db_admin.py stats         - Статистика")
        print("  python3 db_admin.py user <id>     - Детали пользователя")
        print("  python3 db_admin.py extend <id> <days>   - Продлить подписку")
        print("  python3 db_admin.py block <id>    - Заблокировать")
        print("  python3 db_admin.py unblock <id>  - Разблокировать")
        print("\n  Инвайты:")
        print("  python3 db_admin.py invites       - Список инвайт-кодов")
        print("  python3 db_admin.py create_invite [count] [days]  - Создать инвайты")
        sys.exit(1)

    command = sys.argv[1]

    if command == "list":
        list_users()
    elif command == "stats":
        show_stats()
    elif command == "user":
        if len(sys.argv) < 3:
            print("❌ Укажите ID пользователя")
            sys.exit(1)
        show_user(int(sys.argv[2]))
    elif command == "extend":
        if len(sys.argv) < 4:
            print("❌ Укажите ID и количество дней")
            sys.exit(1)
        extend_user(int(sys.argv[2]), sys.argv[3])
    elif command == "block":
        if len(sys.argv) < 3:
            print("❌ Укажите ID пользователя")
            sys.exit(1)
        block_user(int(sys.argv[2]))
    elif command == "unblock":
        if len(sys.argv) < 3:
            print("❌ Укажите ID пользователя")
            sys.exit(1)
        unblock_user(int(sys.argv[2]))
    elif command == "invites":
        list_invites()
    elif command == "create_invite":
        cmd_create_invite(sys.argv[2:])
    else:
        print(f"❌ Неизвестная команда: {command}")
        sys.exit(1)


if __name__ == '__main__':
    main()
