# Runet Niche Analyzer

MVP инструмента для первичного отбора ниш под Рунет. Он принимает пачку до 100 seed-направлений, оценивает спрос, тренд, конкуренцию, бюджет, сложность и выдает CSV/Markdown-отчет с вердиктами.

Сейчас реализован `demo`-провайдер: он не ходит во внешние API, а генерирует детерминированные метрики по тексту направления. Это нужно, чтобы проверить логику, формат отчетов и рабочий процесс без API-ключей.

## Установка

```powershell
python -m pip install -e .
```

## Запуск

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

## Проверки

```powershell
python -m pytest -v
```

## Следующий этап

Следующий практический шаг — добавить реальный провайдер Yandex Search API Wordstat:

- `GetTop` для расширения спроса;
- `GetDynamics` для тренда;
- `GetRegionsDistribution` для региональности;
- SERP-проверку только для финалистов, чтобы не тратить бюджет на мусор.

API-ключи должны передаваться через переменные окружения и не коммититься в репозиторий.

