from sqlalchemy import create_engine, MetaData, Table, inspect

from migrate_ads import DATABASE_URL


def check_db_schema():
    engine = create_engine(DATABASE_URL)
    inspector = inspect(engine)
    
    print("Tables in database:")
    print(inspector.get_table_names())
    
    if 'stories' in inspector.get_table_names():
        print("\nColumns in 'stories' table:")
        for column in inspector.get_columns('stories'):
            print(f"- {column['name']} ({column['type']})")

if __name__ == "__main__":
    check_db_schema()
