from sqlalchemy import inspect, text

from smogcast.storage.db import engine


def main():
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("sensors")}

    with engine.begin() as connection:
        if "status" not in columns:
            connection.execute(
                text(
                    """
                    ALTER TABLE sensors
                    ADD COLUMN status VARCHAR NOT NULL DEFAULT 'active'
                    """
                )
            )

        if "last_backfill_attempt" not in columns:
            connection.execute(
                text(
                    """
                    ALTER TABLE sensors
                    ADD COLUMN last_backfill_attempt DATETIME
                    """
                )
            )

        if "next_retry_at" not in columns:
            connection.execute(
                text(
                    """
                    ALTER TABLE sensors
                    ADD COLUMN next_retry_at DATETIME
                    """
                )
            )

    print("Sensor backfill migration finished.")


if __name__ == "__main__":
    main()
