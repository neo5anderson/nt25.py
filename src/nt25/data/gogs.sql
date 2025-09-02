# Gogs SQLite3

-- # dump
SELECT * FROM sqlite_master;

-- # ls.attach.orphan
SELECT uuid, name
FROM attachment
WHERE
    issue_id = 0
    AND comment_id = 0
    AND release_id = 0;

-- # del.attach.orphan
DELETE FROM attachment
WHERE
    issue_id = 0
    AND comment_id = 0
    AND release_id = 0;