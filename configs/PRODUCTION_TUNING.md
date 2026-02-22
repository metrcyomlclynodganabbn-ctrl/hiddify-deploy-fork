# Hiddify Manager Production Config
# Настроено на основе анализа рабочего VPN (Feb 2026)

## 🔍 INSIGHTS FROM PRODUCTION VPN

Изучены логи рабочего iOS VPN-клиента v4.2.5:
- **VLESS-Reality**: подтверждён рабочий статус
- **Connectivity check**: gstatic.com/generate_204
- **Subscription size**: ~36KB для 19-20 серверов
- **Packet Tunnel Provider**: iOS Network Extension

## 📋 ДОПОЛНИТЕЛЬНЫЕ FALLBACK-DOMENA

На основе анализа блокировок в РФ (февраль 2026):

```json
{
  "primary": {
    "dest": "www.apple.com:443",
    "serverNames": ["apple.com", "www.apple.com"],
    "priority": 1
  },
  "fallbacks": [
    {
      "dest": "www.microsoft.com:443",
      "serverNames": ["microsoft.com", "www.microsoft.com"],
      "priority": 2
    },
    {
      "dest": "cdn.cloudflare.com:443",
      "serverNames": ["cloudflare.com"],
      "priority": 3
    },
    {
      "dest": "www.yahoo.com:443",
      "serverNames": ["yahoo.com", "www.yahoo.com"],
      "priority": 4
    },
    {
      "dest": "www.amazon.com:443",
      "serverNames": ["amazon.com", "www.amazon.com"],
      "priority": 5
    },
    {
      "dest": "www.google.com:443",
      "serverNames": ["google.com", "www.google.com"],
      "priority": 6
    },
    {
      "dest": "www.netflix.com:443",
      "serverNames": ["netflix.com", "www.netflix.com"],
      "priority": 7
    }
  ]
}
```

## ⚡ CONNECTIVITY CHECK

Для проверки соединения (как в production):

```bash
# Test URLs
CONNECTIVITY_CHECK_URLS=(
  "https://www.gstatic.com/generate_204"
  "https://cp.cloudflare.com/generate_204"
  "https://connectivitycheck.gstatic.com/generate_204"
)

# Проверка через curl
for url in "${CONNECTIVITY_CHECK_URLS[@]}"; do
  curl -s -o /dev/null -w "%{http_code}" "$url"
done
```

## 🛡️ RU-SPECIFIC OPTIMIZATIONS (Feb 2026)

### ACTIVE DPI SIGNATURES
- **SNI blocking**: Роскомнадзор блокирует по SNI
- **Deep packet inspection**: анализ TLS handshake
- **Protocol fingerprinting**: Xray/V2Ray detection

### COUNTERMEASURES
1. **REALITY с uTLS**: fingerprint chrome/ios
2. **Hysteria2**: masquerade под QUIC + obfs
3. **Fallback-rotation**: автоматическая смена каждые 24ч
4. **Multi-domain**: 3+ backup домена

## 📊 PRODUCTION METRICS

Из анализа логов:
- **Avg session duration**: 2-8 часов
- **Connection attempts**: 5-10 при старте
- **Success rate**: ~85% после стабилизации
- **Timeout threshold**: 10 секунд для handshake

## 🔧 TUNING PARAMETERS

```yaml
# Hysteria2 - оптимизировано для мобильных РФ
hysteria2:
  quic:
    maxIdleTimeout: 90s      # Увеличено для нестабильных сетей
    keepAlivePeriod: 25s     # Увеличено для 4G
    initConnReceiveWindow: 25M
    maxConnReceiveWindow: 25M

  congestionControl: brutal  # Стабильнее на мобильных

  obfs:
    type: salamander
    password: auto_generate

  masquerade:
    type: proxy
    proxy:
      url: https://www.apple.com
      rewriteHost: true
```

## 🚀 RECOMMENDATIONS

1. **Мониторинг**: проверять connectivity каждые 5 мин
2. **Auto-rotation**: смена REALITY dest при timeout > 3 попытки
3. **Backup protocols**: Hysteria2 как fallback при failure Reality
4. **Graceful degradation**: переключение без разрыва соединения

---

**Updated**: 2026-02-22
**Based on**: Production VPN logs analysis
