from sqlalchemy import text

from backend.app.db.session import engine


EXPECTED_TABLES = {
    "artifacts",
    "artifact_versions",
    "claims",
    "analysis_jobs",
    "provenance_edges",
    "claim_transforms",
    "decision_reports",
}


def main() -> None:
    with engine.connect() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                text(
                    "select table_name from information_schema.tables "
                    "where table_schema = 'public'"
                )
            )
        }
        missing = EXPECTED_TABLES - tables
        if missing:
            raise RuntimeError(f"Missing Tier 1 tables: {sorted(missing)}")

        rls_rows = connection.execute(
            text(
                "select relname, relrowsecurity from pg_class "
                "join pg_namespace on pg_namespace.oid = pg_class.relnamespace "
                "where pg_namespace.nspname = 'public' "
                "and relname = any(:table_names)"
            ),
            {"table_names": sorted(EXPECTED_TABLES)},
        ).all()
        rls = {name: enabled for name, enabled in rls_rows}
        if any(not rls.get(table_name, False) for table_name in EXPECTED_TABLES):
            raise RuntimeError("RLS is not enabled on every Tier 1 table.")

        vector_type = connection.execute(
            text(
                "select format_type(attribute.atttypid, attribute.atttypmod) "
                "from pg_attribute attribute "
                "join pg_class relation on relation.oid = attribute.attrelid "
                "join pg_namespace namespace on namespace.oid = relation.relnamespace "
                "where namespace.nspname = 'public' "
                "and relation.relname = 'artifact_versions' "
                "and attribute.attname = 'embedding'"
            )
        ).scalar_one()
        if vector_type != "vector(1024)":
            raise RuntimeError(f"Unexpected embedding type: {vector_type}")

        row_counts = {
            table_name: connection.execute(
                text(f'select count(*) from public."{table_name}"')
            ).scalar_one()
            for table_name in EXPECTED_TABLES
        }

    print("tier1_tables=ok")
    print(f"table_count={len(EXPECTED_TABLES)}")
    print("rls=enabled")
    print(f"embedding_type={vector_type}")
    print(f"stored_rows={sum(row_counts.values())}")


if __name__ == "__main__":
    main()
