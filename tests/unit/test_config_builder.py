"""Unit тесты для config builder модуля"""

import pytest
from scripts.config.standard_builder import build_standard_config, generate_vless_url
from scripts.config.enhanced_builder import build_enhanced_config, generate_vless_url_enhanced, get_config_recommendation


class TestStandardConfigBuilder:
    """Тесты генератора Standard конфига"""

    def test_build_standard_config_valid(self):
        """Тест генерации Standard конфига"""
        config = build_standard_config(
            user_uuid="test-uuid-123",
            server_address="test.example.com",
            port=443,
            public_key="test-public-key",
            short_id="test-short-id",
            sni="www.apple.com"
        )

        # Проверка структуры
        assert "log" in config
        assert "inbounds" in config
        assert "outbounds" in config
        assert "routing" in config

        # Проверка outbound
        assert config["outbounds"][0]["protocol"] == "vless"
        assert config["outbounds"][0]["tag"] == "proxy"

        # Проверка routing
        assert config["routing"]["domainStrategy"] == "IPIfNonMatch"

    def test_generate_vless_url_valid(self):
        """Тест генерации VLESS URL"""
        url = generate_vless_url(
            user_uuid="test-uuid-123",
            server_address="test.example.com",
            port=443,
            public_key="test-public-key",
            short_id="test-short-id"
        )

        assert url.startswith("vless://")
        assert "test.example.com" in url
        assert "test-uuid-123" in url
        assert "encryption=none" in url
        assert "security=reality" in url


class TestEnhancedConfigBuilder:
    """Тесты генератора Enhanced конфига"""

    def test_build_enhanced_config_valid(self):
        """Тест генерации Enhanced конфига"""
        config = build_enhanced_config(
            user_uuid="test-uuid-123",
            server_address="test.example.com",
            port=443,
            public_key="test-public-key",
            short_id="test-short-id",
            flow="xtls-rprx-vision"
        )

        # Проверка структуры
        assert "outbounds" in config
        assert len(config["outbounds"]) >= 3  # proxy, fragment, direct

        # Проверка flow
        assert config["outbounds"][0]["settings"]["vnext"][0]["users"][0]["flow"] == "xtls-rprx-vision"

        # Проверка minimal routing (только локальные сети напрямую)
        rules = config["routing"]["rules"]
        local_networks_rule = next((r for r in rules if r.get("outboundTag") == "direct"), None)
        assert local_networks_rule is not None

    def test_generate_vless_url_enhanced_valid(self):
        """Тест генерации Enhanced VLESS URL"""
        url = generate_vless_url_enhanced(
            user_uuid="test-uuid-123",
            server_address="test.example.com",
            port=443,
            public_key="test-public-key",
            short_id="test-short-id",
            flow="xtls-rprx-vision"
        )

        assert url.startswith("vless://")
        assert "flow=xtls-rprx-vision" in url
        assert "Hiddify-Enhanced" in url


class TestConfigRecommendation:
    """Тесты рекомендаций по выбору конфига"""

    def test_recommendation_for_russia(self):
        """Тест рекомендаций для РФ"""
        # Для скорости
        mode = get_config_recommendation(location="ru", priority="speed")
        assert mode == "standard"

        # Для приватности
        mode = get_config_recommendation(location="ru", priority="privacy")
        assert mode == "enhanced"

    def test_recommendation_for_china(self):
        """Тест рекомендаций для Китая"""
        mode = get_config_recommendation(location="cn")
        assert mode == "enhanced"

    def test_recommendation_for_iran(self):
        """Тест рекомендаций для Ирана"""
        mode = get_config_recommendation(location="ir")
        assert mode == "enhanced"

    def test_recommendation_by_priority(self):
        """Тест рекомендаций по приоритету"""
        # Скорость
        mode = get_config_recommendation(priority="speed")
        assert mode == "standard"

        # Приватность
        mode = get_config_recommendation(priority="privacy")
        assert mode == "enhanced"

        # Баланс
        mode = get_config_recommendation(priority="balance")
        assert mode == "standard"
