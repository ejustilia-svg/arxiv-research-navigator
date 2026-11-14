# arXiv Research Navigator

Навигатор по научным статьям: собирает статьи arXiv по теме и периоду, отвечает на вопросы
(«какие подходы к X появились за год?») и строит таблицу сравнения (метод, датасет, метрики),
где каждая ячейка подкреплена цитатой из статьи, а непроверенные значения помечены.

Финальный проект курса «Введение в LLM». Отчёт чекпоинта 1 — [docs/checkpoint1_report.md](docs/checkpoint1_report.md).

## Структура

```
config/corpus.yaml            # тема, период, категории и запросы dev-корпуса
src/navigator/collect/        # клиенты источников данных
  arxiv_api.py                #   arXiv API (метаданные) + OAI-PMH (лицензии)
  semantic_scholar.py         #   Semantic Scholar batch API (цитаты, TLDR, venue)
  fulltext.py                 #   arXiv HTML/PDF -> чанки с якорями для цитат
  eval_sets.py                #   QASPER, ArxivDIGESTables
  http.py                     #   паузы под rate limit, ретраи
scripts/collect.py            # CLI сбора данных
data/                         # см. data/STATS.md
docs/                         # отчёты по чекпоинтам
```

## Данные

В репозитории лежат только небольшие файлы: список статей корпуса (`data/processed/papers.parquet`), журнал загрузки полных текстов (`data/processed/fulltext_log.jsonl`) и статистика. Журнал фиксирует, у каких статей скачан полный текст: `fulltext` скачивает все статьи из журнала, поэтому корпус у всех участников одинаковый. Полные тексты статей и эталонные датасеты в репозиторий не входят (объём и лицензии arXiv), их каждый скачивает себе сам.

| Что | Размер | Как получить | Время |
|---|---|---|---|
| Полные тексты статей и фрагменты (`data/raw/`, `data/processed/chunks.jsonl`) | около 85 МБ | `python scripts/collect.py fulltext` | около 20 минут (arXiv разрешает один запрос в 3 секунды) |
| QASPER и ArxivDIGESTables (`data/eval/`) | около 60 МБ | `python scripts/collect.py evalsets` | 1–2 минуты |

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/collect.py fulltext
.venv/bin/python scripts/collect.py evalsets
```

Список статей уже собран, поэтому этапы `meta` и `s2` запускать не нужно. Они заново ищут статьи в arXiv и перезаписывают `papers.parquet`, и корпус может измениться: за это время в arXiv появляются новые статьи. Команда `all` запускает все этапы подряд, включая эти два.

Этапы можно прерывать и запускать снова: `fulltext` докачивает только те статьи, файлов которых ещё нет на диске. После правок парсера фрагменты можно пересобрать из скачанных файлов без сети: `python scripts/collect.py chunks`.

Ключ Semantic Scholar (необязательно, снимает ограничение частоты запросов) задаётся в переменной окружения `S2_API_KEY`. В репозиторий его класть нельзя.
