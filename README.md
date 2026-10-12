# Lab 5: Multi-container приложение с Docker Compose

Приложение из трёх сервисов: Flask API, PostgreSQL, Redis.

## Запуск
1. Скопируйте шаблон и заполните значения:
   cp .env.example .env
2. Запустите всё одной командой:
   docker compose up --build -d
3. Проверьте статус:
   docker compose ps

## Endpoints (порт задаётся в .env, API_PORT)
- GET  /            информация о приложении
- GET  /health      health check
- GET  /db-test     подключение к PostgreSQL
- GET  /cache-test  подключение к Redis
- POST /users       создать пользователя (JSON: name, email)
- GET  /users       список пользователей
- GET  /users/:id   пользователь (сначала из кеша Redis, затем из БД)

## Пример
curl -X POST http://localhost:5005/users -H "Content-Type: application/json" -d '{"name":"Alice","email":"alice@example.com"}'
curl http://localhost:5005/users/1

## Архитектура
- db: PostgreSQL 15, данные в volume postgres_data, healthcheck pg_isready
- redis: Redis 7, данные в volume redis_data, healthcheck redis-cli ping
- api: Flask, стартует после того, как db и redis станут healthy
- Сервисы находятся в сети backend и обращаются друг к другу по именам (db, redis)
- Секреты хранятся в .env, который добавлен в .gitignore

## Остановка
docker compose down        (данные сохраняются)
docker compose down -v     (удаляет также volumes)
