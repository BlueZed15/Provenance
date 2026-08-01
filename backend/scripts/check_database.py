from sqlalchemy import text

from backend.app.db.session import engine


def main() -> None:
    with engine.connect() as connection:
        select_result = connection.execute(text("select 1")).scalar_one()
        vector_enabled = connection.execute(
            text(
                "select exists ("
                "select 1 from pg_extension where extname = 'vector'"
                ")"
            )
        ).scalar_one()

    print(f"database_select={select_result}")
    print(f"vector_extension={bool(vector_enabled)}")


if __name__ == "__main__":
    main()
