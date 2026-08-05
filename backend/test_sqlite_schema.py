from sqlalchemy import Column, Integer, create_engine, event
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class TestTable(Base):
    __tablename__ = 'test'
    __table_args__ = {'schema': 'cvai'}
    id = Column(Integer, primary_key=True)

engine = create_engine("sqlite:///:memory:")
@event.listens_for(engine, "connect")
def do_connect(dbapi_connection, connection_record):
    dbapi_connection.execute("ATTACH DATABASE ':memory:' AS cvai")

Base.metadata.create_all(bind=engine)
print("SUCCESS")
