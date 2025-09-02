import shutil
from nt25 import SQLite, fio, __data_path__

file = __data_path__ + "/gogs.sql"

kHost = "//192.168.55.5/docker/Git/"
kGogsDB = kHost + "gogs.db"

kTmpPath = kHost + "gogs/data/tmp"
kAttachmentPath = "gogs/data/attachments"


def main():
  s = SQLite(file)
  s.open(kGogsDB)

  t, rs = s.exec("ls.attach.orphan")  # type: ignore

  if rs is not None:
    orphan = {}

    for r in rs:
      uuid = r[0]
      orphan[uuid] = {"name": r[1]}

    fl = fio.ls(kHost + kAttachmentPath, lambda f: f in orphan)

    total = 0
    for f in fl:
      if f[0] in orphan:
        o = orphan[f[0]]
        o["path"] = f[1]
        o["size"] = f[2]

        try:
          shutil.move(f[1], kTmpPath)
          total += f[2]
        except Exception:
          print(f"move {o['name']} ({o['path']}) failed")

    length = len(orphan)
    if length > 0:
      s.exec("del.attach.orphan", result=False)
      print(f"Purged {len(orphan)} files, {total / 1024 / 1024 / 1024.0:.1f}GB")
      s.close(commit=True)
    else:
      print("Everybody is fine")
      s.close(commit=False)


if __name__ == "__main__":
  main()
