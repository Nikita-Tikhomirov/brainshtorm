# Runet Niche Analyzer

MVP инструмента для первичного отбора ниш под Рунет. Он принимает пачку до 100 seed-направлений, оценивает спрос, тренд, конкуренцию, бюджет, сложность и выдает CSV/Markdown-отчет с вердиктами.

Есть два режима:

- `Yandex Wordstat API` — пользователь вставляет API key и folder ID прямо в интерфейсе, ключ и параметры сохраняются локально на компьютере.
- `Demo` — не ходит во внешние API, а генерирует детерминированные метрики по тексту направления.

SERP-анализ подключен как второй этап: сначала пачка ранжируется по Wordstat/Demo-метрикам, затем выдача проверяется только для финалистов.

AI-вердикт подключен как третий этап: GPT или DeepSeek анализирует финалистов по метрикам и SERP, затем добавляет практический вывод в отчет.

## Установка

```powershell
python -m pip install -e .
```

## Запуск

Самый удобный вариант — ярлык на рабочем столе:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\create_desktop_shortcut.ps1
```

После этого запускайте `Runet Niche Analyzer` двойным кликом с рабочего стола. Ярлык поднимает Streamlit на `http://localhost:8501` и открывает браузер. Если приложение уже запущено, второй сервер не стартует, просто откроется браузер.

Ручной запуск:

```powershell
.\run_app.cmd
```

Прямой запуск Streamlit:

```powershell
python -m streamlit run src/brainshtorm/app.py
```

CLI-режим:

```powershell
python -m brainshtorm.cli examples/directions.csv --output-dir out/demo --provider demo
```

Результаты:

- `out/demo/analysis.csv` — таблица с оценками.
- `out/demo/report.md` — отчет с ранжированием, идеями продуктов, шагами продвижения и рисками.

## Формат CSV

Обязательные колонки:

- `direction` — seed-направление.
- `region` — регион анализа.
- `budget_rub` — бюджет запуска в рублях.
- `max_difficulty` — максимальная допустимая сложность от 1 до 10.
- `project_type` — тип проекта.

Поддерживаемые типы проекта:

- `seo_site`
- `leadgen`
- `service`
- `telegram`
- `infoproduct`
- `marketplace`

Пример:

```csv
direction,region,budget_rub,max_difficulty,project_type
ремонт роботов пылесосов,Москва,150000,6,leadgen
курсы нейросетей,Россия,100000,7,infoproduct
```

## Работа через интерфейс

1. Запустите Streamlit.
2. В боковой панели выберите режим `Yandex Wordstat API` или `Demo`.
3. Для реального режима вставьте `Yandex API key` и `Yandex folder ID`.
4. Вставьте список направлений по одному на строку.
5. Выберите регион, бюджет, сложность и тип проекта.
6. Включите `Проверять выдачу финалистов`, если нужен SERP-анализ.
7. Выберите, сколько финалистов и результатов выдачи проверять.
8. Включите `Генерировать AI-вердикт финалистов`, если нужен AI-вывод.
9. Выберите `GPT` или `DeepSeek`, вставьте API key и при необходимости измените модель.
10. Нажмите `Сохранить параметры`, если хотите просто запомнить настройки без анализа.
11. Нажмите `Запустить анализ`.
12. Скачайте `analysis.csv` или `report.md`.

Для API-ключа нужен сервисный аккаунт Yandex Cloud с ролью `search-api.webSearch.user` и ключом со scope `yc.search-api.execute`.

Настройки хранятся в профиле пользователя:

```text
%USERPROFILE%\.brainshtorm\settings.json
```

На Windows Yandex/OpenAI/DeepSeek API key и folder ID записываются через DPAPI-защиту текущего пользователя. Файл настроек находится вне репозитория и не попадает в git. Логи фонового запуска пишутся в `out\logs`.

## Проверки

```powershell
python -m pytest -v
```

## Следующий этап

Реальный провайдер Yandex Search API Wordstat уже подключен:

- `GetTop` для спроса и похожих запросов;
- `GetDynamics` для тренда;
- `GetRegionsDistribution` для региональности.

SERP-проверка использует `WebSearch.Search` (`/v2/web/search`) и XML-ответ из `rawData`. Она добавляет в таблицу:

- `serp_difficulty` — оценка сложности выдачи;
- `serp_delta` — поправка к итоговому score;
- `top_domains` — первые домены из выдачи.

AI-слой уже добавлен через GPT/OpenAI Responses API и DeepSeek Chat Completions API. Ключ вставляется в интерфейсе и сохраняется локально в защищенном файле настроек.
Следующий практический шаг — добавить кэширование SERP/AI-ответов и более удобный экспорт продуктовых гипотез.

API-ключи не сохраняются в репозитории.
