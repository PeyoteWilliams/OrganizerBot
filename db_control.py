import psycopg2
import sqlalchemy
from sqlalchemy import MetaData, and_, create_engine, select, delete
from db_create import user, task, task_to_remind
from datetime import datetime, date
from bot_exceptions import UserAlreadyExists, UserNotExistsYet

# Connect to PostgreSQL on localhost with psycopg2 DBAPI
engine = create_engine(f"postgresql+psycopg2://postgres:f528b25b85we8v4n1u8m4k1m4yntb@localhost/organizer")
engine.connect()
metadata = MetaData()


def insert_user(user_id: int, nick: str, offset: int = 0):
    ins = user.insert().values(
        id=user_id,
        nick=nick[:30],
        created_on=datetime.now(),
        timezone=offset,
    )
    conn = engine.connect()
    try:
        r = conn.execute(ins)
    except sqlalchemy.exc.IntegrityError as e:
        if isinstance(e.orig, psycopg2.errors.UniqueViolation):
            raise UserAlreadyExists
        else:
            raise e


def insert_day_task(text: str, day: date, user_id: int):
    ins = task.insert().values(
        text=text,
        day=day,
        user_id=user_id,
    )
    conn = engine.connect()
    try:
        r = conn.execute(ins)
    except sqlalchemy.exc.IntegrityError as e:
        if isinstance(e.orig, psycopg2.errors.ForeignKeyViolation):
            raise UserNotExistsYet
        else:
            raise e


def insert_reminder(task_id: int, time: datetime):
    ins = task_to_remind.insert().values(
        id=task_id,
        remind_moment=time,
    )
    conn = engine.connect()
    r = conn.execute(ins)


def get_task_id(text: str, day: date, user_id: int):
    conn = engine.connect()
    s = select([task]).where(and_(
        task.c.day == day, task.c.text == text, task.c.user_id == user_id
    ))
    return conn.execute(s).fetchall()[-1][0]


def get_day_tasks(day: date):
    conn = engine.connect()
    s = select([task]).where(
        task.c.day == day
    )
    return conn.execute(s).fetchall()


def get_day_tasks_with_reminders(day: date):
    conn = engine.connect()
    s = select([task.c.id, task.c.text, task.c.day, task_to_remind.c.remind_moment]).where(
        task.c.day == day
    ).outerjoin(task_to_remind)
    return conn.execute(s).fetchall()


def get_day_tasks_by_user_id(day: date, user_id: int):
    conn = engine.connect()
    s = select([task]).where(and_(
        task.c.day == day, task.c.user_id == user_id
    ))
    return conn.execute(s).fetchall()


def get_day_tasks_with_reminders_by_user_id(day: date, user_id: int):
    conn = engine.connect()
    s = select([task.c.id, task.c.text, task.c.day, task_to_remind.c.remind_moment]).where(and_(
        task.c.day == day, task.c.user_id == user_id
    )).outerjoin(task_to_remind)
    return conn.execute(s).fetchall()


def get_reminders_before_target_time_with_ids(time: datetime):
    conn = engine.connect()
    s = select([task_to_remind.c.id, task_to_remind.c.remind_moment, task.c.text, task.c.user_id]).where(
        task_to_remind.c.remind_moment <= time
    ).outerjoin(task_to_remind)
    return conn.execute(s).fetchall()


def get_user_timezone(user_id: int):
    conn = engine.connect()
    s = select([user.c.timezone]).where(
        user.c.id == user_id
    )
    result = conn.execute(s).fetchone()
    return result[0] if result else None


def delete_day_task(task_id: int):
    delete_reminders_by_id(task_id)
    d = delete(task).where(
        task.c.id == task_id
    )
    conn = engine.connect()
    conn.execute(d)


def delete_reminders_by_id(task_id: int):
    d = delete(task_to_remind).where(
        task_to_remind.c.id == task_id
    )
    conn = engine.connect()
    conn.execute(d)


def delete_reminders_before_target_time(time: datetime):
    d = delete(task_to_remind).where(
        task_to_remind.c.remind_moment <= time
    )
    conn = engine.connect()
    conn.execute(d)


def change_user_timezone(user_id: int, timezone: int):
    from sqlalchemy import update

    stmt = (
        update(user).
            where(user.c.id == user_id).
            values(timezone=timezone)
    )
    conn = engine.connect()
    conn.execute(stmt)
