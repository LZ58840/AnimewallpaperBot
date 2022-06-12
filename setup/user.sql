DROP USER IF EXISTS 'animewallpaperbot'@'localhost';

SET @create_user = CONCAT('CREATE USER "animewallpaperbot"@"localhost" IDENTIFIED BY "', @pwd, '";');
PREPARE create_user_stmt FROM @create_user;
EXECUTE create_user_stmt;
DEALLOCATE PREPARE create_user_stmt;
