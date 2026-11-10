"""极简"自愈式"字段迁移（仅 SQLite）。

比赛/演示环境用 SQLite，没有引入 Alembic。而 `Base.metadata.create_all()`
只会建缺失的表，不会给已存在的表补字段——新增列后老库会直接报
"no such column"。这里在启动时读 PRAGMA 检查一遍，缺什么补什么：

- 幂等：列已存在直接跳过，可反复执行；
- 非阻断：补字段失败只打日志，不阻止应用启动。

新增字段时，在 _EXTRA_COLUMNS 里登记一行即可。
"""

from sqlalchemy import text
from sqlalchemy.engine import Engine

_EXTRA_COLUMNS: dict[str, dict[str, str]] = {
    "reports": {
        "question_reviews": "JSON",
    },
}


def ensure_extra_columns(engine: Engine) -> None:
    if not str(engine.url).startswith("sqlite"):
        return

    for table, columns in _EXTRA_COLUMNS.items():
        try:
            with engine.begin() as conn:
                rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
                if not rows:
                    continue  # 表还没建（首次启动由 create_all 负责）
                existing = {row[1] for row in rows}
                for name, ddl in columns.items():
                    if name in existing:
                        continue
                    try:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                        print(f"🛠️  自愈迁移：已补齐 {table}.{name}")
                    except Exception as e:  # noqa: BLE001
                        print(f"⚠️  自愈迁移失败 {table}.{name}: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"⚠️  自愈迁移跳过 {table}: {e}")
