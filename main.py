import csv
import sys
import urllib.request
import gzip
from io import BytesIO

def main():
    config_file = 'config_1.csv'
    # config_file = 'config_2.csv'
    # config_file = 'config_3.csv'
    # config_file = 'config_4.csv'
    

    config = read_config(config_file)
    validate_config(config)
    print_config(config)

def read_config(filename):
    config = {}
    
    try:
        with open(filename, 'r', encoding='utf-8') as f: #r значит для чтения
            reader = csv.reader(f)
            header = next(reader)
            
            if len(header) != 2 or header[0] != 'param' or header[1] != 'value':
                raise ValueError("Некорректный формат CSV. Ожидается 'param,value'")
            
            for row in reader:
                if len(row) != 2:
                    raise ValueError(f"Некорректная строка в CSV: {row}")
                config[row[0]] = row[1]
                
    except FileNotFoundError: #Ловим исключения
        print(f"ОШИБКА: Файл '{filename}' не найден!")
        sys.exit(1)
    except ValueError as e:
        print(f"ОШИБКА: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ОШИБКА при чтении файла: {e}")
        sys.exit(1)
    
    return config

#Проверяем не написаны ли какие-нибудь глупости
def validate_config(config):
    required_params = ['package_name', 'repository_url', 'repo_mode', 'package_version']
    #repo_mode - режим работы с репозиторием. prod Для реальных и test для хихихаха
    
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

if __name__ == '__main__':
    main()