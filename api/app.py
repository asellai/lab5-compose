from flask import Flask, jsonify, request
import psycopg2
import redis
import os
import json

app = Flask(__name__)

# Конфигурация из переменных окружения (их передаёт docker compose из .env)
DB_CONFIG = {
    "host": os.environ["DB_HOST"],
    "port": os.environ["DB_PORT"],
    "database": os.environ["DB_NAME"],
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
}

REDIS_HOST = os.environ["REDIS_HOST"]
REDIS_PORT = int(os.environ["REDIS_PORT"])

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def init_db():
    """Создаёт таблицу users при старте, если её ещё нет."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


@app.route("/")
def home():
    return jsonify({"app": "Lab5 API", "status": "running"})


@app.route("/health")
def health():
    return jsonify({"status": "healthy"})


@app.route("/db-test")
def db_test():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        cur.close()
        conn.close()
        return jsonify({"status": "success", "database": version})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/cache-test")
def cache_test():
    try:
        redis_client.set("test_key", "test_value", ex=60)
        value = redis_client.get("test_key")
        return jsonify({"status": "success", "redis": "connected", "test_value": value})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/users", methods=["POST"])
def create_user():
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    email = data.get("email")
    if not name or not email:
        return jsonify({"error": "name and email are required"}), 400

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (name, email) VALUES (%s, %s) RETURNING id",
            (name, email),
        )
        user_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        return jsonify({"id": user_id, "name": name, "email": email}), 201
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return jsonify({"error": "email already exists"}), 409
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/users", methods=["GET"])
def list_users():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, name, email FROM users ORDER BY id")
        users = [{"id": r[0], "name": r[1], "email": r[2]} for r in cur.fetchall()]
        cur.close()
        conn.close()
        return jsonify({"count": len(users), "users": users})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/users/<int:user_id>")
def get_user(user_id):
    # 1. Сначала смотрим в кеш (Redis)
    cached = redis_client.get(f"user:{user_id}")
    if cached:
        return jsonify({"source": "cache", "user": json.loads(cached)})

    # 2. Если в кеше нет, идём в БД
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, name, email FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if not row:
        return jsonify({"error": "user not found"}), 404

    user = {"id": row[0], "name": row[1], "email": row[2]}
    # 3. Кладём в кеш на 60 секунд
    redis_client.set(f"user:{user_id}", json.dumps(user), ex=60)
    return jsonify({"source": "database", "user": user})


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
