import psycopg2


class UserAlreadyExists(psycopg2.errors.UniqueViolation):
    """Raised when user in table 'user' already exists"""
    pass


class UserNotExistsYet(Exception):
    """Raised when user in table 'user' not exists"""
    pass


class WrongDayFormat(Exception):
    """Raised when user input date in wrong format"""
    pass


class WrongTimeFormat(Exception):
    """Raised when user input time in wrong format"""
    pass


class Only24HoursInADay(WrongTimeFormat):
    """Raised when user input hour number bigger than 24"""
    pass


class Only60MinutesInAHour(WrongTimeFormat):
    """Raised when user input minute number bigger than 60"""
    pass


class BugInCheckTime(Exception):
    """Raised when time check function is not working properly"""
    pass


class UselessDay(Exception):
    """Raised when a day without tasks"""
    pass
