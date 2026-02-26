"""Config модуль для генерации конфигураций"""

from .standard_builder import build_standard_config, generate_vless_url
from .enhanced_builder import build_enhanced_config, generate_vless_url_enhanced, get_config_recommendation

__all__ = [
    'build_standard_config',
    'generate_vless_url',
    'build_enhanced_config',
    'generate_vless_url_enhanced',
    'get_config_recommendation'
]
