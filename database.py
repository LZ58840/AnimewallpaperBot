# https://stackoverflow.com/a/54847238
import pymysql


class DatabaseContext:
    def __init__(self, config_db):
        self.config_db = config_db
        self.con = None
        self.cur = None

    def __enter__(self):
        self.con = pymysql.connect(**self.config_db)
        self.cur = self.con.cursor()
        return self.cur

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.con.close()
