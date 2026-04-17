"""
Скрипт для проверки TCP соединения с YooKassa API
"""
import socket
import sys

def test_tcp_connection(host, port, timeout=5):
    """Проверяет TCP соединение с указанным хостом и портом"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        print(f"  ОШИБКА: {e}")
        return False

def main():
    print("=" * 50)
    print("  Тест TCP соединения с YooKassa API")
    print("=" * 50)
    print()
    
    # IP адреса и домен для проверки
    hosts = [
        ("109.235.165.99", 443, "IP адрес 1"),
        ("185.71.78.133", 443, "IP адрес 2"),
        ("api.yookassa.ru", 443, "Доменное имя"),
    ]
    
    all_success = True
    
    for host, port, description in hosts:
        print(f"Проверка {description} ({host}:{port})...")
        if test_tcp_connection(host, port):
            print(f"  ✓ УСПЕХ: TCP соединение установлено")
        else:
            print(f"  ✗ ОШИБКА: TCP соединение не установлено (таймаут или блокировка)")
            all_success = False
        print()
    
    print("=" * 50)
    if all_success:
        print("  Все проверки пройдены успешно!")
    else:
        print("  Некоторые проверки не прошли")
        print()
        print("Возможные причины:")
        print("  1. Файрвол Windows блокирует исходящие соединения")
        print("     Решение: запустите scripts\\fix_yookassa_firewall.bat от имени администратора")
        print()
        print("  2. Провайдер/хостинг блокирует доступ к российским IP")
        print("     Решение: обратитесь к провайдеру для разблокировки")
        print()
        print("  3. Проблемы с сетевыми настройками сервера")
    print("=" * 50)
    
    return 0 if all_success else 1

if __name__ == "__main__":
    sys.exit(main())

