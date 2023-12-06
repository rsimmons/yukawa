from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, text

from app import app

metadata = MetaData()
engine = create_engine(app.config['DB_URL'])

def ping_db():
    with engine.connect() as conn:
        return conn.execute(text('select 1')).scalar()

def print_ddl():
    from sqlalchemy import create_mock_engine

    def dump(sql, *multiparams, **params):
        print(sql.compile(dialect=engine.dialect))

    engine = create_mock_engine(app.config['DB_URL'], dump)
    metadata.create_all(engine, checkfirst=False)

user = Table('user', metadata,
    Column('id', Integer, primary_key=True),
    Column('email', String(255), nullable=False),
)
