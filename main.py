import csv
import sys
import urllib.request
import re
import ssl

def main():
    # config_file = 'config_1.csv'
    config_file = 'config_2.csv'
    
    config = read_config(config_file)
    validate_config(config)
    print_config(config)
    
    # Определяем тип ссылки и обрабатываем
    url = config['repository_url']
    package_name = config['package_name']
    package_version = config.get('package_version', '')
    
    if 'pkgs.alpinelinux.org' in url:
        # Это прямая ссылка на пакет Alpine
        print(f"Обнаружена прямая ссылка на Alpine пакет")
        process_alpine_url(url, package_name, package_version)
    elif 'github.com' in url or 'gitlab.com' in url:
        # Это репозиторий на Github/Gitlab
        print(f"Обнаружена ссылка на репозиторий Github/Gitlab")
        process_repo_url(url, package_name, package_version)
    else:
        print(f"ОШИБКА: Неизвестный тип ссылки '{url}'")
        sys.exit(1)

def read_config(filename):
    config = {}
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            
            if len(header) != 2 or header[0] != 'param' or header[1] != 'value':
                raise ValueError("Некорректный формат CSV. Ожидается 'param,value'")
            
            for row in reader:
                if len(row) != 2:
                    raise ValueError(f"Некорректная строка в CSV: {row}")
                config[row[0]] = row[1]
                
    except FileNotFoundError:
        print(f"ОШИБКА: Файл '{filename}' не найден!")
        sys.exit(1)
    except ValueError as e:
        print(f"ОШИБКА: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ОШИБКА при чтении файла: {e}")
        sys.exit(1)
    
    return config

def validate_config(config):
    required_params = ['package_name', 'repository_url', 'repo_mode', 'package_version']
    
    for param in required_params:
        if param not in config:
            print(f"ОШИБКА: Отсутствует обязательный параметр '{param}'")
            sys.exit(1)
    
    if config['repo_mode'] not in ['test', 'prod']:
        print(f"ОШИБКА: Неподдерживаемое значение repo_mode='{config['repo_mode']}'. Допустимые значения: 'test', 'prod'")
        sys.exit(1)
    
    if 'ascii_output' in config:
        if config['ascii_output'].lower() not in ['true', 'false']:
            print(f"ОШИБКА: Некорректное значение ascii_output='{config['ascii_output']}'. Допустимые значения: 'true', 'false'")
            sys.exit(1)

def print_config(config):
    print("Конфигурация")
    for param, value in config.items():
        print(f"{param} = {value}")
    print()

def fetch_url(url):
    """Простая функция для загрузки страницы"""
    try:
        print(f"Загружаю страницу: {url}")
        request = urllib.request.Request(url)
        request.add_header('User-Agent', 'Mozilla/5.0')
        
        # Создаем SSL контекст который игнорирует проверку сертификатов (для macOS)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        with urllib.request.urlopen(request, timeout=10, context=ssl_context) as response:
            html = response.read().decode('utf-8')
        return html
    except Exception as e:
        print(f"ОШИБКА при загрузке страницы {url}: {e}")
        return None

def parse_alpine_page(html, package_name, package_version):
    """Парсим HTML страницу пакета Alpine Linux"""
    
    # Ищем имя пакета
    name_match = re.search(r'<th class="header">Package</th>\s*<td>([^<]+)</td>', html)
    if not name_match:
        print("ОШИБКА: Не удалось найти имя пакета на странице")
        return None
    
    found_name = name_match.group(1).strip()
    print(f"Найденное имя пакета: {found_name}")
    
    # Проверяем имя
    if found_name != package_name:
        print(f"ОШИБКА: Имя пакета не совпадает. Ожидалось '{package_name}', найдено '{found_name}'")
        return None
    
    # Ищем версию
    version_match = re.search(r'<th class="header">Version</th>\s*<td>\s*<strong>([^<]+)</strong>', html)
    if not version_match:
        print("ОШИБКА: Не удалось найти версию пакета")
        return None
    
    found_version = version_match.group(1).strip()
    print(f"Найденная версия: {found_version}")
    
    # Проверяем версию если указана
    if package_version and package_version != '':
        if found_version != package_version:
            print(f"ОШИБКА: Версия не совпадает. Ожидалось '{package_version}', найдено '{found_version}'")
            return None
    
    # Ищем зависимости
    depends_match = re.search(r'<summary>Depends \((\d+)\)</summary>.*?<ul class="pure-menu-list">(.*?)</ul>', html, re.DOTALL)
    
    if not depends_match:
        print("Зависимостей не найдено")
        return []
    
    depends_count = depends_match.group(1)
    depends_html = depends_match.group(2)
    
    print(f"Найдено зависимостей: {depends_count}")
    
    # Парсим список зависимостей
    dependencies = []
    dep_items = re.findall(r'<li class="pure-menu-item">.*?>(.*?)</a>', depends_html, re.DOTALL)
    
    for dep in dep_items:
        dep_clean = dep.strip()
        if dep_clean:
            dependencies.append(dep_clean)
    
    return dependencies

def process_alpine_url(url, package_name, package_version):
    """Обрабатываем прямую ссылку на пакет Alpine"""
    html = fetch_url(url)
    if not html:
        sys.exit(1)
    
    dependencies = parse_alpine_page(html, package_name, package_version)
    
    if dependencies is None:
        sys.exit(1)
    
    print("\n=== ЗАВИСИМОСТИ ===")
    if len(dependencies) == 0:
        print("Зависимостей нет")
    else:
        for i, dep in enumerate(dependencies, 1):
            print(f"{i}. {dep}")

def extract_package_from_repo_url(url):
    """Извлекаем имя пакета из URL репозитория"""
    # Убираем trailing slash
    url = url.rstrip('/')
    
    # Берем последнюю часть URL
    parts = url.split('/')
    package_name = parts[-1]
    
    print(f"Извлеченное имя пакета из URL: {package_name}")
    return package_name

def search_alpine_package(package_name, package_version):
    """Ищем пакет на pkgs.alpinelinux.org"""
    
    branch = ["/edge", "/v3.22", "/v3.21", "/v3.20", "/v3.19", "/v3.18", 
              "/v3.17", "/v3.16", "/v3.15", "/v3.14"]
    repository = ["/community", "/main", "/testing"]
    architecture = ["/x86_64", "/x86", "/s390x", "/riscv64", "/ppc65le", 
                   "/loongarch64", "/armv7", "/armhf", "/aarch64"]
    
    base_url = "https://pkgs.alpinelinux.org/package"
    
    print(f"\nИщу пакет '{package_name}' на pkgs.alpinelinux.org...")
    
    # Перебираем все комбинации
    for b in branch:
        for r in repository:
            for a in architecture:
                url = f"{base_url}{b}{r}{a}/{package_name}"
                
                print(f"Проверяю: {url}")
                
                html = fetch_url(url)
                if html:
                    # Проверяем что страница содержит пакет (не 404)
                    if '<th class="header">Package</th>' in html:
                        print(f"✓ Пакет найден!")
                        
                        dependencies = parse_alpine_page(html, package_name, package_version)
                        
                        if dependencies is not None:
                            print("\n=== ЗАВИСИМОСТИ ===")
                            if len(dependencies) == 0:
                                print("Зависимостей нет")
                            else:
                                for i, dep in enumerate(dependencies, 1):
                                    print(f"{i}. {dep}")
                            return True
    
    print(f"ОШИБКА: Пакет '{package_name}' не найден ни в одной комбинации branch/repository/architecture")
    return False

def process_repo_url(url, package_name, package_version):
    """Обрабатываем ссылку на репозиторий Github/Gitlab"""
    
    # Извлекаем имя пакета из URL (последняя часть)
    extracted_name = extract_package_from_repo_url(url)
    
    # Ищем на Alpine
    found = search_alpine_package(extracted_name, package_version)
    
    if not found:
        sys.exit(1)

if __name__ == '__main__':
    main()