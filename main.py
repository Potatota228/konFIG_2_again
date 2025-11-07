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
        print(" РЕЖИМ ТЕСТИРОВАНИЯ \n")
        process_test_mode(config)
    else:
        print(" РЕЖИМ PROD \n")
        process_prod_mode(config)

#                                ----------------------------- КОНФИГ -----------------------------#

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


#                           ----------------------------- РАБОТА С URL -----------------------------#

def fetch_url(url):
    
    try:
        print(f"Загрузка страницы: {url}")
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

def parse_alpine_page(html, package_name, package_version, is_root):
    
    
    # Ищем имя пакета
    """
    <th class="header">Package</th>	    ищет точный кусок HTML: тег <th> с атрибутом class="header" и текстом Package.
                                        Это заголовок таблицы.

    \s*	                                ноль или больше пробельных символов (пробелы, табы, переводы строк).
                                        Нужно, потому что между </th> и <td> может быть перенос строки или пробел.

    <td>	                            ищем следующий тег <td> — это ячейка таблицы с данными пакета.

    ([^<]+)	                            захватывающая группа. Берём все символы, кроме <, до закрывающего тега.
                                        Это и есть имя пакета.
                                        
    </td>	                            закрывающий тег таблицы.
    """
    name_match = re.search(r'<th class="header">Package</th>\s*<td>([^<]+)</td>', html)
    if not name_match:
        print("ОШИБКА: Не удалось найти имя пакета на странице")
        return None
    
    found_name = name_match.group(1).strip()
    print(f"Найденное имя пакета: {found_name}")
    if is_root:
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

    """
    <summary>Depends \((\d+)\)</summary>    ищет тег <summary>, в котором написано Depends (5) —
                                            то есть слово “Depends”, пробел, число в скобках.

    (\d+)	                                захватывает это число (5, 10, 23 — сколько угодно цифр).

    .*?	                                    означает “любой текст, даже на нескольких строках,
                                            как можно меньше символов” — чтобы перепрыгнуть от
                                             </summary> до <ul ...>

    <ul class="pure-menu-list">(.*?)</ul>	находит тег <ul> со списком зависимостей и забирает его содержимое.

    re.DOTALL	                            делает так, чтобы . в регулярке захватывал все символы,
                                            включая переводы строк, иначе HTML на нескольких строках не сработает.
    """
    depends_match = re.search(
        r'<summary>Depends \((\d+)\)</summary>.*?<ul class="pure-menu-list">(.*?)</ul>',
        html,
        re.DOTALL
    )
    """ group(1) — число зависимостей (например "5")

        group(2) — HTML-код <li>...</li> со всеми зависимостями.
    """
    
    if not depends_match:
        print("Зависимостей не найдено")
        return []
    
    depends_count = depends_match.group(1)
    depends_html = depends_match.group(2)
    
    print(f"Найдено зависимостей: {depends_count}")
    
    """
    <a	            начало тега ссылки
    [^>]+	        любые символы кроме > (то есть атрибуты внутри тега)
    href="([^"]+)"	ищет атрибут href="..." и захватывает сам URL внутрь первой группы (...)
    [^>]*	        пропускает оставшиеся атрибуты до >
    >([^<]+)</a>	берёт текст внутри ссылки (имя пакета) — это вторая группа (...).
    """
    # Парсим имя и ссылку каждой зависимости
    dependencies = []
    dep_items = re.findall(
        r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>',
        depends_html
    )
    
    for href, name in dep_items:
        dep_name = name.strip()
        dep_url = "https://pkgs.alpinelinux.org" + href.strip()
        print(f"    {dep_name} ({dep_url})")
        dependencies.append([dep_name,dep_url])
    
    return dependencies

#                           ----------------------------- РАБОТА С РЕПОЙ -----------------------------#

def extract_package_from_repo_url(url):
    
    # Убираем trailing slash
    url = url.rstrip('/')
    
    # Берем последнюю часть URL
    parts = url.split('/')
    package_name = parts[-1]
    
    print(f"Извлеченное имя пакета из URL: {package_name}")
    return package_name

def find_alpine_package(package_name):
    branch = ["/edge", "/v3.22", "/v3.21", "/v3.20", "/v3.19", "/v3.18", 
              "/v3.17", "/v3.16", "/v3.15", "/v3.14"]
    repository = ["/community", "/main", "/testing"]
    architecture = ["/x86_64", "/x86", "/s390x", "/riscv64", "/ppc65le", 
                   "/loongarch64", "/armv7", "/armhf", "/aarch64"]
     
    base_url = "https://pkgs.alpinelinux.org/package"
    
    print(f"Поиск пакета '{package_name}' на pkgs.alpinelinux.org...")
    
    # Перебираем все комбинации
    for b in branch:
        for r in repository:
            for a in architecture:
                url = f"{base_url}{b}{r}{a}/{package_name}"
                
                html = fetch_url(url)
                if html:
                    # Проверяем что страница содержит пакет (не 404)
                    if '<th class="header">Package</th>' in html:
                        print(f" Пакет найден: {url}")
                        return url, html
    
    print(f" Пакет '{package_name}' не найден")
    return None, None

#                           ----------------------------- РАБОТА В PROD -----------------------------#

def process_prod_mode(config):
    
    
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
        found_url, html = find_alpine_package(name)
        start_package = [name, found_url]
    else:
        print(f"ОШИБКА: Неизвестный тип ссылки '{url}'")
        sys.exit(1)
    
    # Строим граф зависимостей
    graph = build_dependency_graph_bfs(start_package, package_version)
    
    # Выводим граф
    print_graph(graph)

def build_dependency_graph_bfs(start_package, package_version=''):
    
    
    graph = {}
    queue = [start_package]
    visited = set()
    
    print("\n ПОСТРОЕНИЕ ГРАФА ЗАВИСИМОСТЕЙ (BFS) \n")
    
    while queue:
        current_package = queue.pop(0)
        pkg_name, pkg_url = current_package
        
        # Если уже обработали — пропускаем
        if pkg_name in visited:
            print(f"Пакет '{pkg_name}' уже обработан, пропускем")
            continue
        
        print(f"\nОбрабатываем пакет: {pkg_name} ({pkg_url})")
        
        if not pkg_url:
            print(f"Пакет '{pkg_name}' не найден, зависимости = []")
            graph[tuple(current_package)] = []
            visited.add(pkg_name)
            continue
        
        html = fetch_url(pkg_url)
        if not html:
            print(f"Не удалось загрузить страницу пакета '{pkg_name}'")
            graph[tuple(current_package)] = []
            visited.add(pkg_name)
            continue
        
        # Парсим зависимости
        if pkg_name == start_package[0]:
            dependencies = parse_alpine_page(html, pkg_name, package_version, is_root=True)
        else:
            dependencies = parse_alpine_page(html, pkg_name, package_version, is_root=False)

        if dependencies is None:
            dependencies = []
        
        # Сохраняем зависимости в граф
        graph[tuple(current_package)] = dependencies
        if current_package!=start_package:
            print(f"Зависимости пакета '{pkg_name}': {[d[0] for d in dependencies]}")
        
        # Добавляем зависимости в очередь
        for dep in dependencies:
            dep_name, dep_url = dep
            if check_cycle(dep, current_package, graph):
                print(f" Цикл: '{pkg_name}' зависит от '{dep_name}', но '{dep_name}' (прямо или транзитивно) зависит от '{pkg_name}'")
            elif dep_name not in visited:
                print(f"Добавляем в очередь: {dep_name}")
                queue.append(dep)
        
        visited.add(pkg_name)
    
    return graph

#                           ----------------------------- РАБОТА В TEST -----------------------------#

def read_test_repository(filepath):
    
    print(f"Читаем тестовый репозиторий из файла: {filepath}\n")
    
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

def process_test_mode(config):
    
    
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

def build_test_graph_bfs(start_package, test_repo):
    
    graph = {}
    queue = []
    visited = set()
    
    queue.append(start_package)
    
    print("\n ПОСТРОЕНИЕ ГРАФА ЗАВИСИМОСТЕЙ (BFS) \n")
    
    while len(queue) > 0:
        current_package = queue.pop(0)
        
        if current_package in visited:
            print(f"Пакет '{current_package}' уже обработан, пропускаем")
            continue
        
        print(f"Обрабатываем пакет: {current_package}")
        
        # Получаем зависимости из тестового репозитория
        if current_package not in test_repo:
            print(f" Пакет '{current_package}' не найден в репозитории!")
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
                print(f" ВНИМАНИЕ: Обнаружен цикл! Пакет '{current_package}' зависит от '{dep}', но '{dep}' (прямо или транзитивно) зависит от '{current_package}'")
            elif dep not in visited:
                print(f"Добавляю в очередь: {dep}")
                queue.append(dep)
        
        visited.add(current_package)
        print()
    
    return graph

#                           ----------------------------- ОБЩАЯ РАБОТА С ГРАФОМ -----------------------------#

def check_cycle(dep, current_package, graph):
    
    dep_name = dep[0]
    current_name = current_package[0]
    
    # Если зависимости ещё нет в графе — цикла нет
    if dep_name not in [pkg[0] for pkg in graph.keys()]:
        return False
    
    check_queue = [dep]
    checked = set()
    
    while check_queue:
        check_pkg = check_queue.pop(0)
        check_name = check_pkg[0]
        
        if check_name in checked:
            continue
        checked.add(check_name)
        
        if check_name == current_name:
            return True
        
        # Добавляем зависимости для проверки
        for pkg, deps in graph.items():
            if pkg[0] == check_name:
                for next_dep in deps:
                    if next_dep[0] not in checked:
                        check_queue.append(next_dep)
    
    return False

def print_graph(graph):
    
    print("\n ГРАФ ЗАВИСИМОСТЕЙ \n")
    for package, dependencies in graph.items():
        pkg_name =  package
        print(f"{pkg_name}:")
        
        if not dependencies:
            print("  (нет зависимостей)")
        else:
            for dep_name in dependencies:
                print(f"   {dep_name}")
        print()

if __name__ == '__main__':
    main()