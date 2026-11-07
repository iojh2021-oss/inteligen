import os, sqlite3
from pathlib import Path
from datetime import datetime, timezone

def _db():
    path = Path(os.getenv("DATABASE_PATH", "data/memory.sqlite3"))
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        world TEXT NOT NULL,
        prompt TEXT NOT NULL,
        result TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    conn.commit()
    return conn

def save(world: str, prompt: str, result: str):
    with _db() as conn:
        conn.execute("INSERT INTO memories(world,prompt,result,created_at) VALUES(?,?,?,?)",
            (world, prompt[:8000], result[:12000], datetime.now(timezone.utc).isoformat()))

def recent(limit: int = 20):
    with _db() as conn:
        rows = conn.execute("SELECT world,prompt,result,created_at FROM memories ORDER BY id DESC LIMIT ?", (min(max(limit,1),100),)).fetchall()
    return [{"world":r[0],"prompt":r[1],"result":r[2],"created_at":r[3]} for r in rows]
