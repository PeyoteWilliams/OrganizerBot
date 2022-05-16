import sqlalchemy
from sqlalchemy import MetaData, Table, String, Integer, Column, Text, DateTime, Boolean, BigInteger, ForeignKey, Date,\
    SmallInteger
from datetime import datetime
from sqlalchemy import create_engine

# Подключение к серверу PostgreSQL на localhost с помощью psycopg2 DBAPI
engine = create_engine("postgresql+psycopg2://postgres:f528b25b85we8v4n1u8m4k1m4yntb@localhost/organizer")
engine.connect()
metadata = MetaData()

user = Table('user', metadata,
             Column('id', BigInteger(), primary_key=True, autoincrement=False),
             Column('nick', String(30), nullable=False),
             Column('created_on', DateTime(), default=datetime.now),
             Column('timezone', SmallInteger(), default=0, nullable=False)
             )

task = Table("task", metadata,
             Column("id", Integer(), primary_key=True, autoincrement=True),
             Column("text", Text(), nullable=False),
             Column("day", Date(), nullable=False, index=True),
             Column("user_id", ForeignKey("user.id")),
             )

task_to_remind = Table("task_to_remind", metadata,
                       Column("id", ForeignKey("task.id"), primary_key=True),
                       Column("remind_moment", DateTime(), nullable=False),
                       )

metadata.create_all(engine)
