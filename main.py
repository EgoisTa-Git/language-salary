import datetime
import os
import time
from operator import itemgetter

import requests
from dotenv import load_dotenv
from terminaltables import DoubleTable

SJ_API_URL = 'https://api.superjob.ru/2.0/vacancies/'
HH_API_URL = 'https://api.hh.ru/vacancies'
LANGUAGES = [
    'JavaScript',
    'Python',
    'Java',
    'TypeScript',
    'C#',
    'PHP',
    'C++',
    'Shell',
    'C',
    'Ruby',
]


def get_hh_vacancies(language, *args):
    payload = {
        'text': f'Программист {language}',
        'area': 1,
        'only_with_salary': True,
        'period': 30,
    }
    while True:
        response = requests.get(HH_API_URL, params=payload)
        response.raise_for_status()
        page_data = response.json()
        page = page_data['page']
        pages = page_data['pages']
        print(f'Collecting data for {language}: page {page} from {pages}')
        if page >= pages:
            print('Work done!')
            yield page_data['items']
            break
        payload['page'] = page + 1
        yield page_data['items']


def get_sj_vacancies(language, api_key):
    headers = {
        'X-Api-App-Id': api_key,
    }
    search_from = datetime.datetime.now() - datetime.timedelta(days=30)
    unix_time = int(time.mktime(search_from.timetuple()))
    payload = {
        'date_published_from': unix_time,
        'keyword': f'Программист {language}',
        'town': 4,
        'no_agreement': 1,
        'page': 0,
    }
    while True:
        response = requests.get(SJ_API_URL, headers=headers, params=payload)
        response.raise_for_status()
        page_data = response.json()
        page = payload['page']
        print(f'Collecting data for {language}: page {page}')
        if not page_data['more']:
            print('Work done!')
            yield page_data['objects']
            break
        payload['page'] = page + 1
        yield page_data['objects']


def predict_rub_salary(salary):
    salary_from = salary[0]
    salary_to = salary[1]
    currency_rur = salary[2]
    if not currency_rur:
        return None
    elif not salary_from:
        return int(salary_to * 0.8)
    elif not salary_to:
        return int(salary_from * 1.2)
    else:
        return int((salary_from + salary_to) / 2)


def get_salary_from_hh(vacancy):
    salary = vacancy['salary']
    currency_rur = True if salary['currency'] == 'RUR' else False
    return salary['from'], salary['to'], currency_rur


def get_salary_from_sj(vacancy):
    sal_from = vacancy['payment_from'] if vacancy['payment_from'] > 0 else None
    sal_to = vacancy['payment_to'] if vacancy['payment_to'] > 0 else None
    currency_rur = True if vacancy['currency'] == 'rub' else False
    return sal_from, sal_to, currency_rur


def get_found_vacancies(get_vacancies, get_salary):
    vacancies_found = {}
    for lang in LANGUAGES:
        vacancies_per_lang = {
            'vacancies_found': 0,
            'vacancies_processed': 0,
            'average_salary': 0,
        }
        average_salaries = []
        for vacancies in get_vacancies(lang, sj_api_key):
            for vacancy in vacancies:
                vacancies_per_lang['vacancies_found'] += 1
                predicted_salary = predict_rub_salary(
                    get_salary(vacancy)
                )
                if predicted_salary:
                    average_salaries.append(predicted_salary)
        try:
            vacancies_per_lang['average_salary'] = int(
                sum(average_salaries) / len(average_salaries)
                )
            vacancies_per_lang['vacancies_processed'] = len(average_salaries)
        except ZeroDivisionError:
            vacancies_per_lang['average_salary'] = 0
            vacancies_per_lang['vacancies_processed'] = 0
        vacancies_found[lang] = vacancies_per_lang
    return vacancies_found


def format_table(vacancy_statistics, table_name):
    data = []
    for key, value in vacancy_statistics.items():
        data_string = [key]
        data_string.extend(list(value.values()))
        data.append(data_string)
    data = sorted(data, key=itemgetter(3), reverse=True)
    data.insert(
        0,
        [
            'Язык программирования',
            'Вакансий найдено',
            'Вакансий обработано',
            'Средняя зарплата',
        ],
    )
    table = DoubleTable(data, table_name)
    table.justify_columns = {
        0: 'left',
        1: 'center',
        2: 'center',
        3: 'right'
    }
    return table.table


if __name__ == '__main__':
    load_dotenv()
    sj_api_key = os.getenv('SJ_SECRET_KEY')
    hh_vacancies = get_found_vacancies(get_hh_vacancies, get_salary_from_hh)
    sj_vacancies = get_found_vacancies(get_sj_vacancies, get_salary_from_sj)
    print(format_table(hh_vacancies, ' HeadHunter Moscow '))
    print(format_table(sj_vacancies, ' SuperJob Moscow '))
