import re
import sqlite3


def getColumns(sql):
  sql = sql.splitlines()

  head = False
  tail = False
  while len(sql) > 0:
    if not head:
      h = sql.pop(0)
      if h.endswith("("):
        head = True

    if not tail:
      t = sql.pop(len(sql) - 1)
      if t.endswith(";") or t.endswith(")"):
        tail = True

    if head and tail:
      break

  return sql


class SQLite:
  def __init__(self, file=None):
    self.sql = {}

    if file is not None:
      self.parse(file)

  def parse(self, file):
    with open(file, encoding="utf-8") as f:
      content = f.read()

      sKey = re.findall("-- # (.*)\n", content)
      sSQL = re.split("-- #.*\n", content)

      if len(sSQL) > len(sKey):
        del sSQL[0]

      self.sql = {}
      for i in range(len(sKey)):
        self.sql[sKey[i]] = sSQL[i]

      return self.sql

  def getKeys(self):
    return self.sql.keys()

  def getTemplate(self, key):
    return self.sql[key]

  def diffTemplate(self, name, key):
    result = True

    sql = f'SELECT sql FROM sqlite_master WHERE name = "{name}";'
    _, c = self.execute(sql)  # type: ignore

    if c:
      c = getColumns(c[0][0])
      tsql = getColumns(self.sql[key])
      result = c != tsql

    return result

  def open(self, db):
    print(f"Working with db: {db}")
    self.db = sqlite3.connect(db)
    self.cursor = self.db.cursor()

  def exec(self, key, result=True):
    return self.execute(self.sql[key], result)

  def execBatch(self, key):
    return self.batch(self.sql[key])

  def key2str(self, key):
    if key not in self.sql:
      return "> {0} not found\n\n".format(key)

    s = ""
    try:
      t, r = self.exec(key)  # type: ignore

      if t is not None:
        if r is not None and len(r) > 0:
          rows = "\n".join(map(lambda x: str(x), r))
          s = "> {0}\n{1}\n{2}\n\n".format(key, t, rows)
        else:
          s = "> {0}\n{1}\n\n".format(key, t)
      else:
        s = "> {0}\n\n".format(key)

    except Exception as e:
      s = "> {0}, bad: {1}!\n\n".format(key, e)

    return s

  def commit(self):
    if self.db is not None:
      self.db.commit()

  def batch(self, sql):
    if self.cursor is not None and self.db is not None:
      try:
        self.cursor.executescript(sql)

        if self.db.total_changes > 0:
          print("SQLite> db.changed", self.db.total_changes)

        self.db.commit()

      except Exception as e:
        print(e)

  def _execute(self, sql, result=True, multiSQL=False):
    ret = ()

    if self.cursor is not None and self.db is not None:
      try:
        if multiSQL:
          res = self.cursor.executescript(sql)
        else:
          res = self.cursor.execute(sql)

        if self.db.total_changes > 0:
          print("SQLite> db.changed", self.db.total_changes)

        if res and res.description:
          title = []
          for rt in res.description:
            title.append(rt[0])

          rows = res.fetchall()
          ret = (tuple(title), rows)
      except Exception as e:
        print(e)
        ret = (e, None)

    if result:
      return ret

  def executes(self, sql, result=True):
    return self._execute(sql, result, multiSQL=True)

  def execute(self, sql, result=True):
    return self._execute(sql, result, multiSQL=False)

  def close(self, commit=False):
    if self.db:
      if commit:
        self.db.commit()

      self.db.close()
      self.db = None
