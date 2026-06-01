# Runet Niche Analyzer

MVP инструмента для первичного отбора ниш под Рунет. Он принимает пачку до 100 seed-направлений, оценивает спрос, тренд, конкуренцию, бюджет, сложность и выдает CSV/Markdown-отчет с вердиктами.

Есть два режима:

- `Yandex Wordstat API` — пользователь вставляет API key и folder ID прямо в интерфейсе, ключ используется только в памяти текущего запуска.
- `Demo` — не ходит во внешние API, а генерирует детерминированные метрики по тексту направления.

## Установка

```powershell
python -m pip install -e .
```

## Запуск

Веб-интерфейс:

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
6. Нажмите `Запустить анализ`.
7. Скачайте `analysis.csv` или `report.md`.

Для API-ключа нужен сервисный аккаунт Yandex Cloud с ролью `search-api.webSearch.user` и ключом со scope `yc.search-api.execute`.

## Проверки

```powershell
python -m pytest -v
```

## Следующий этап

Реальный провайдер Yandex Search API Wordstat уже подключен:

- `GetTop` для спроса и похожих запросов;
- `GetDynamics` для тренда;
- `GetRegionsDistribution` для региональности.

Следующий практический шаг — добавить SERP-проверку только для финалистов, чтобы не тратить бюджет на мусор.

API-ключи не сохраняются в репозитории. В интерфейсе они используются только в памяти текущего запуска.
