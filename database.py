# https://stackoverflow.com/a/54847238
# https://stackoverflow.com/questions/8720179/nesting-python-context-managers
# https://rednafi.github.io/digressions/python/2020/03/26/python-contextmanager.html
import pymysql
import pymysql.cursors
from contextlib import contextmanager


class DatabaseContext:
    def __init__(self, config_db):
        self.config_db = config_db
        self.con = None
        self.cur = None

    def __enter__(self):
        self.con = pymysql.connect(**self.config_db)
        self.cur = self.con.cursor(pymysql.cursors.DictCursor)
        return self.cur

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.con.commit()
        self.cur.close()
        self.con.close()


@contextmanager
def database_ctx(config_db, cur_type=pymysql.cursors.DictCursor):
    con = pymysql.connect(**config_db)
    cur = con.cursor(cur_type)
    try:
        yield cur
    finally:
        con.commit()
        cur.close()
        con.close()
