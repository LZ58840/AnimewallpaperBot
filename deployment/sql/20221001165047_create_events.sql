USE animewallpaper;

CREATE EVENT IF NOT EXISTS
    ClearArchivedSubmissions
ON SCHEDULE EVERY 1 DAY
DO
    DELETE FROM submission
    WHERE UNIX_TIMESTAMP() - created >= 15780000;
