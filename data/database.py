import pymysql
import pymysql.cursors
from contextlib import contextmanager

# https://stackoverflow.com/a/54847238
# https://rednafi.github.io/digressions/python/2020/03/26/python-contextmanager.html


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
