import csv
import sys
import urllib.request
import re
import ssl

def main():
    config_file = 'config_1.csv'
    
    config = read_config(config_file)
    validate_config(config)
    print_config(config)
    
    repo_mode = config['repo_mode']
    
    if repo_mode == 'test':
        # Режим тестирования - читаем граф из файла
        print("=== РЕЖИМ ТЕСТИРОВАНИЯ ===\n")
        process_test_mode(config)
    else:
        # Режим prod - работаем с реальными пакетами
        print("=== РЕЖИМ PROD ===\n")
        process_prod_mode(config)

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
    depends_match = re.search(
        r'<summary>Depends \((\d+)\)</summary>.*?<ul class="pure-menu-list">(.*?)</ul>',
        html,
        re.DOTALL
    )
    
    if not depends_match:
        print("Зависимостей не найдено")
        return []
    
    depends_count = depends_match.group(1)
    depends_html = depends_match.group(2)
    
    print(f"Найдено зависимостей: {depends_count}")
    
    # Парсим имя и ссылку каждой зависимости
    dependencies = []
    dep_items = re.findall(
        r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>',
        depends_html
    )
    
    for href, name in dep_items:
        dep_name = name.strip()
        dep_url = "https://pkgs.alpinelinux.org" + href.strip()
        print(f"  → {dep_name} ({dep_url})")
        dependencies.append([dep_name,dep_url])
    
    return dependencies

def extract_package_from_repo_url(url):
    """Извлекаем имя пакета из URL репозитория"""
    # Убираем trailing slash
    url = url.rstrip('/')
    
    # Берем последнюю часть URL
    parts = url.split('/')
    package_name = parts[-1]
    
    print(f"Извлеченное имя пакета из URL: {package_name}")
    return package_name

def find_alpine_package(package_name):
    """Ищем пакет на pkgs.alpinelinux.org и возвращаем URL если найден"""
    
    branch = ["/edge", "/v3.22", "/v3.21", "/v3.20", "/v3.19", "/v3.18", 
              "/v3.17", "/v3.16", "/v3.15", "/v3.14"]
    repository = ["/community", "/main", "/testing"]
    architecture = ["/x86_64", "/x86", "/s390x", "/riscv64", "/ppc65le", 
                   "/loongarch64", "/armv7", "/armhf", "/aarch64"]
    
    base_url = "https://pkgs.alpinelinux.org/package"
    
    print(f"Ищу пакет '{package_name}' на pkgs.alpinelinux.org...")
    
    # Перебираем все комбинации
    for b in branch:
        for r in repository:
            for a in architecture:
                url = f"{base_url}{b}{r}{a}/{package_name}"
                
                html = fetch_url(url)
                if html:
                    # Проверяем что страница содержит пакет (не 404)
                    if '<th class="header">Package</th>' in html:
                        print(f"✓ Пакет найден: {url}")
                        return url, html
    
    print(f"✗ Пакет '{package_name}' не найден")
    return None, None

def build_dependency_graph_bfs(start_package, package_version=''):
    """
    Строим граф зависимостей используя BFS (без рекурсии)
    Возвращает словарь {package_name: [список зависимостей]}
    """
    
    graph = {}  # Граф зависимостей
    queue = []  # Очередь для BFS
    visited = set()  # Посещенные пакеты
    
    # Добавляем стартовый пакет в очередь
    queue.append(start_package)
    
    print("\n=== ПОСТРОЕНИЕ ГРАФА ЗАВИСИМОСТЕЙ (BFS) ===\n")
    
    while len(queue) > 0:
        # Берем первый элемент из очереди
        current_package = queue.pop(0)
        
        # Если уже обработали этот пакет - пропускаем
        if current_package in visited:
            print(f"Пакет '{current_package[0]}' уже обработан, пропускаю")
            continue
        
        print(f"\nОбрабатываю пакет: {current_package}")
        
        # Ищем пакет и получаем его зависимости
        url = current_package[1]
        
        if url is None:
            print(f"Пакет '{current_package}' не найден, зависимости = []")
            graph[current_package] = []
            visited.add(current_package)
            continue
        
        # Парсим зависимости
        dependencies = parse_alpine_page(fetch_url(url), current_package, package_version if current_package == start_package else '')
        
        if dependencies is None:
            dependencies = []
        
        # Сохраняем зависимости в граф
        graph[current_package] = dependencies
        
        print(f"Зависимости пакета '{current_package}': {dependencies}")
        
        # Добавляем зависимости в очередь
        for dep in dependencies:
            # Проверяем, не создаст ли эта зависимость цикл
            if check_cycle(dep, current_package, graph):
                print(f"⚠ ВНИМАНИЕ: Обнаружен цикл! Пакет '{current_package}' зависит от '{dep[1]}', но '{dep[1]}' (прямо или транзитивно) зависит от '{current_package}'")
            elif dep not in visited:
                print(f"Добавляю в очередь: {dep}")
                queue.append(dep)
        
        # Отмечаем пакет как обработанный
        visited.add(current_package)
    
    return graph

def print_graph(graph):
    """Выводим граф в читаемом виде"""
    print("\n=== ГРАФ ЗАВИСИМОСТЕЙ ===\n")
    
    for package, dependencies in graph.items():
        print(f"{package}:")
        if len(dependencies) == 0:
            print("  (нет зависимостей)")
        else:
            for dep in dependencies:
                print(f"  → {dep}")
        print()

def process_prod_mode(config):
    """Обработка в режиме prod - работа с реальными пакетами"""
    
    url = config['repository_url']
    package_name = config['package_name']
    package_version = config.get('package_version', '')
    
    # Определяем откуда начинать
    if 'pkgs.alpinelinux.org' in url:
        print(f"Обнаружена прямая ссылка на Alpine пакет")
        start_package = [package_name, url]
    elif 'github.com' in url or 'gitlab.com' in url:
        print(f"Обнаружена ссылка на репозиторий Github/Gitlab")
        name = extract_package_from_repo_url(url)
        start_package = [name, find_alpine_package(name)]
    else:
        print(f"ОШИБКА: Неизвестный тип ссылки '{url}'")
        sys.exit(1)
    
    # Строим граф зависимостей
    graph = build_dependency_graph_bfs(start_package, package_version)
    
    # Выводим граф
    print_graph(graph)

def read_test_repository(filepath):
    """Читаем тестовый репозиторий из файла"""
    print(f"Читаю тестовый репозиторий из файла: {filepath}\n")
    
    graph = {}
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                
                # Пропускаем пустые строки и комментарии
                if not line or line.startswith('#'):
                    continue
                
                # Формат: PACKAGE: DEP1, DEP2, DEP3
                # или PACKAGE: (если нет зависимостей)
                
                if ':' not in line:
                    print(f"ОШИБКА: Некорректная строка (нет ':'): {line}")
                    continue
                
                parts = line.split(':', 1)
                package = parts[0].strip()
                
                dependencies = []
                if len(parts) > 1 and parts[1].strip():
                    deps_str = parts[1].strip()
                    dependencies = [d.strip() for d in deps_str.split(',')]
                
                graph[package] = dependencies
                print(f"Загружен пакет: {package} -> {dependencies}")
        
        print(f"\nВсего загружено пакетов: {len(graph)}\n")
        return graph
        
    except FileNotFoundError:
        print(f"ОШИБКА: Файл '{filepath}' не найден!")
        sys.exit(1)
    except Exception as e:
        print(f"ОШИБКА при чтении файла: {e}")
        sys.exit(1)

def check_cycle(dep, current_package, graph):
    """
    Проверяем, не создаст ли добавление зависимости dep цикл
    Проходим по графу от dep и смотрим, не встретим ли мы current_package
    """
    
    if dep not in graph:
        # Зависимость еще не обработана, цикла нет
        return False
    
    # Список для обхода (простой BFS для проверки)
    check_queue = [dep]
    checked = set()
    
    while len(check_queue) > 0:
        check_pkg = check_queue.pop(0)
        
        if check_pkg in checked:
            continue
        
        checked.add(check_pkg)
        
        # Если нашли current_package в зависимостях dep - это цикл!
        if check_pkg == current_package:
            return True
        
        # Добавляем зависимости для дальнейшей проверки
        if check_pkg in graph:
            for next_dep in graph[check_pkg]:
                if next_dep not in checked:
                    check_queue.append(next_dep)
    
    return False

def build_test_graph_bfs(start_package, test_repo):
    """
    Строим граф зависимостей для тестового репозитория используя BFS
    """
    
    graph = {}
    queue = []
    visited = set()
    
    queue.append(start_package)
    
    print("\n=== ПОСТРОЕНИЕ ГРАФА ЗАВИСИМОСТЕЙ (BFS) ===\n")
    
    while len(queue) > 0:
        current_package = queue.pop(0)
        
        if current_package in visited:
            print(f"Пакет '{current_package}' уже обработан, пропускаю")
            continue
        
        print(f"Обрабатываю пакет: {current_package}")
        
        # Получаем зависимости из тестового репозитория
        if current_package not in test_repo:
            print(f"⚠ Пакет '{current_package}' не найден в репозитории!")
            graph[current_package] = []
            visited.add(current_package)
            continue
        
        dependencies = test_repo[current_package]
        graph[current_package] = dependencies
        
        print(f"Зависимости: {dependencies}")
        
        # Добавляем зависимости в очередь
        for dep in dependencies:
            # Проверяем, не создаст ли эта зависимость цикл
            if check_cycle(dep, current_package, graph):
                print(f"⚠ ВНИМАНИЕ: Обнаружен цикл! Пакет '{current_package}' зависит от '{dep}', но '{dep}' (прямо или транзитивно) зависит от '{current_package}'")
            elif dep not in visited:
                print(f"Добавляю в очередь: {dep}")
                queue.append(dep)
        
        visited.add(current_package)
        print()
    
    return graph

def process_test_mode(config):
    """Обработка в режиме test - работа с тестовым репозиторием"""
    
    repository_url = config['repository_url']
    package_name = config['package_name']
    
    # В тестовом режиме repository_url - это путь к файлу
    test_repo = read_test_repository(repository_url)
    
    # Проверяем что стартовый пакет есть в репозитории
    if package_name not in test_repo:
        print(f"ОШИБКА: Пакет '{package_name}' не найден в тестовом репозитории!")
        sys.exit(1)
    
    # Строим граф
    graph = build_test_graph_bfs(package_name, test_repo)
    
    # Выводим граф
    print_graph(graph)

if __name__ == '__main__':
    main()