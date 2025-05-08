import psycopg2
import os

DB_NAME = os.getenv("DB_NAME", "final_project")
DB_USER = os.getenv("DB_USER", "put_your_username_here")
DB_PASSWORD = os.getenv("DB_PASSWORD", "put_your_password_here")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

def run_explain_analyze(query):
    with psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
                          host=DB_HOST, port=DB_PORT) as conn:
        with conn.cursor() as cur:
            cur.execute(f"EXPLAIN (ANALYZE, FORMAT JSON) {query}")
            result = cur.fetchone()[0]
            return result

def run_query_rows(query):
    with psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
                          host=DB_HOST, port=DB_PORT) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            columns = [desc[0] for desc in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchmany(20)]
            return rows
