#!/usr/bin/env python3
"""
Тест пропускной способности Hiddify Manager
"""

import os
import sys
import time
import requests
from dotenv import load_dotenv

load_dotenv()

PANEL_DOMAIN = os.getenv("PANEL_DOMAIN", "panel.yourdomain.ru")

def test_download_speed():
    """Тест скорости скачивания"""

    # URL для теста (можно использовать любой быстрый CDN)
    test_url = f"https://{PANEL_DOMAIN}/speedtest"

    print("🧪 Тест скорости скачивания...")

    start_time = time.time()

    try:
        # Скачивание 10MB файла
        response = requests.get(test_url, stream=True, timeout=30)
        total_size = 0

        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                total_size += len(chunk)

        end_time = time.time()
        duration = end_time - start_time

        # Расчёт скорости в Mbps
        speed_mbps = (total_size * 8) / (duration * 1000000)

        print(f"   📊 Скорость: {speed_mbps:.2f} Mbps")
        print(f"   ⏱️  Время: {duration:.2f} сек")
        print(f"   📦 Размер: {total_size / 1024 / 1024:.2f} MB")

        return speed_mbps

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return 0

def test_upload_speed():
    """Тест скорости загрузки"""

    print("\n🧪 Тест скорости загрузки...")

    # Генерация тестовых данных (1MB)
    test_data = b"x" * (1024 * 1024)

    start_time = time.time()

    try:
        response = requests.post(
            f"https://{PANEL_DOMAIN}/speedtest/upload",
            data=test_data,
            timeout=30
        )

        end_time = time.time()
        duration = end_time - start_time

        # Расчёт скорости в Mbps
        speed_mbps = (len(test_data) * 8) / (duration * 1000000)

        print(f"   📊 Скорость: {speed_mbps:.2f} Mbps")
        print(f"   ⏱️  Время: {duration:.2f} сек")

        return speed_mbps

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return 0

def test_latency():
    """Тест задержки (ping)"""

    print("\n🧪 Тест задержки...")

    latencies = []

    for i in range(5):
        start_time = time.time()

        try:
            requests.get(f"https://{PANEL_DOMAIN}/ping", timeout=5)

            end_time = time.time()
            latency = (end_time - start_time) * 1000  # в мс
            latencies.append(latency)

        except Exception as e:
            print(f"   ❌ Попытка {i+1} неудачна: {e}")

    if latencies:
        avg_latency = sum(latencies) / len(latencies)
        print(f"   📊 Средняя задержка: {avg_latency:.2f} ms")
        print(f"   📊 Мин: {min(latencies):.2f} ms")
        print(f"   📊 Макс: {max(latencies):.2f} ms")
        return avg_latency
    else:
        print("   ❌ Не удалось измерить задержку")
        return 0

def main():
    """Главная функция"""

    print("🚀 Запуск тестов скорости...")
    print(f"   Панель: {PANEL_DOMAIN}")
    print()

    # Тесты
    download_speed = test_download_speed()
    upload_speed = test_upload_speed()
    latency = test_latency()

    # Итоги
    print("\n" + "="*50)
    print("📊 ИТОГИ:")
    print(f"   Скорость скачивания: {download_speed:.2f} Mbps")
    print(f"   Скорость загрузки: {upload_speed:.2f} Mbps")
    print(f"   Задержка: {latency:.2f} ms")

    # Проверка требований
    print("\n✅ Проверка требований:")
    print(f"   Скорость >50 Mbps: {'✅' if download_speed > 50 else '❌'}")
    print(f"   Задержка <100 ms: {'✅' if latency < 100 else '❌'}")

    return 0

if __name__ == '__main__':
    sys.exit(main())
