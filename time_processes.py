import datetime
import re
from bot_exceptions import *


class TimeDispatcher:
    @staticmethod
    def format_time(time: datetime.datetime, offset: int = 0):
        """Convert datetime.datetime to string making adjustments for offset"""
        offset = 0 if offset is None else offset
        return (time + datetime.timedelta(hours=3+offset)).strftime("%H:%M")

    @staticmethod
    def check_time(time):  # переписать через регулярки
        """
        Try to make separately integer hours and minutes from user input
        """
        match = re.fullmatch(r"(?:\d|[0-1]\d|2[0-3])(?:\D(?:\d|[0-5]\d))?", time)
        if match:
            splitted = re.split(r"\D", match.group())
            if len(splitted) == 1:
                return int(splitted[0]), 0
            elif len(splitted) == 2:
                return tuple(map(int, splitted))
            else:
                raise BugInCheckTime
        else:
            raise WrongTimeFormat

    @staticmethod
    def convert_local_notification_time_and_date_to_global(time: datetime.time, date: datetime.date, offset: int = 0):
        """Convert user's local notification time and date separately to global datetime for storage in database"""
        offset = 0 if offset is None else offset
        return datetime.datetime.combine(date, time) - datetime.timedelta(hours=3 + offset)

    @staticmethod
    def today_userside(offset: int = 0):
        """Make user local 'today' for storage in database"""
        offset = 0 if offset is None else offset
        global_date = (datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(hours=3+offset)).date()

        return global_date

    @staticmethod
    def format_day_tasks(task_list: list, offset: int = 0):
        """ Format tasks from list or raise exception if list is empty"""
        offset = 0 if offset is None else offset
        return_string = ""
        if task_list:
            return_string += "День " + task_list[0][2].strftime('%d.%m') + "\n"
            for i in range(len(task_list)):
                return_string += f"{i + 1}) "
                if task_list[i][3]:
                    return_string += f"{(task_list[i][3] + datetime.timedelta(hours=3+offset)).strftime('%H:%M')}🔔 "
                return_string += task_list[i][1] + "\n"
                datetime.datetime.now().strftime("%h %M")
        else:
            raise UselessDay
        return return_string
