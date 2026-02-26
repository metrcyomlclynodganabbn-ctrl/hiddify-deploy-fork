# Hiddify Manager Auto-Deploy Makefile
# Удобные команды для разработки и деплоя

.PHONY: help install dev-install test test-cov lint typecheck check clean run-bot deploy health

# Default target
help:
	@echo "Доступные команды:"
	@echo "  make install         - Установить зависимости"
	@echo "  make dev-install     - Установить dev зависимости"
	@echo "  make test            - Запустить тесты"
	@echo "  make test-cov        - Запустить тесты с покрытием"
	@echo "  make lint            - Проверить стиль кода (flake8)"
	@echo "  make typecheck       - Проверить типы (mypy)"
	@echo "  make check           - Полная проверка (lint + typecheck + test)"
	@echo "  make clean           - Очистить временные файлы"
	@echo "  make run-bot         - Запустить бота"
	@echo "  make deploy          - Деплой на сервер"
	@echo "  make health          - Проверить здоровье системы"

# Установка зависимостей
install:
	pip install -r requirements.txt

# Установка dev зависимостей
dev-install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

# Запуск тестов
test:
	pytest tests/ -v --tb=short

# Тесты с покрытием
test-cov:
	pytest tests/ -v --cov=scripts --cov-report=term-missing --cov-report=xml --cov-report=html

# Проверка стиля кода (flake8)
lint:
	flake8 scripts/ --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 scripts/ --count --exit-zero --max-complexity=10 --max-line-length=100 --statistics

# Проверка типов (mypy)
typecheck:
	mypy scripts/ --ignore-missing-imports --no-strict-optional

# Полная проверка
check: lint typecheck test
	@echo "✅ Все проверки пройдены!"

# Очистка временных файлов
clean:
	find . -type f -name '*.pyc' -delete
	find . -type f -name '*.pyo' -delete
	find . -type d -name '__pycache__' -delete
	find . -type d -name '*.egg-info' -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf coverage.xml
	@echo "🧹 Очистка завершена"

# Запуск бота
run-bot:
	python3 scripts/monitor_bot.py

# Деплой на сервер
deploy:
	bash scripts/deploy.sh

# Проверка здоровья
health:
	python3 scripts/health_check.py
