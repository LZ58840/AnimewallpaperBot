USE animewallpaper;

CREATE TABLE IF NOT EXISTS subreddit (
    name VARCHAR(20) PRIMARY KEY ,
    updated INT
);

CREATE TABLE IF NOT EXISTS submission (
    id VARCHAR(10) PRIMARY KEY ,
    url VARCHAR(255) NOT NULL ,
    subreddit VARCHAR(20) NOT NULL ,
    author VARCHAR(20) NOT NULL ,
    created INT NOT NULL ,
    removed INT NOT NULL DEFAULT 0 ,
    tries INT NOT NULL DEFAULT 0,
    tries_at INT ,

    FOREIGN KEY (subreddit)
        REFERENCES subreddit(name)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS image (
    id INT AUTO_INCREMENT PRIMARY KEY ,
    url VARCHAR(255) NOT NULL ,
    submission_id VARCHAR(10) NOT NULL ,
    downloaded INT NOT NULL DEFAULT 0 ,
    downloaded_at INT ,
    width INT NOT NULL DEFAULT -1,
    height INT NOT NULL DEFAULT -1,

    FOREIGN KEY (submission_id)
        REFERENCES submission(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS 4histogram (
    id INT PRIMARY KEY ,
    red JSON NOT NULL ,
    green JSON NOT NULL ,
    blue JSON NOT NULL ,

    FOREIGN KEY (id)
        REFERENCES image(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS dhash (
    id INT PRIMARY KEY ,
    red BIT(64) NOT NULL ,
    green BIT(64) NOT NULL ,
    blue BIT(64) NOT NULL ,

    FOREIGN KEY (id)
        REFERENCES image(id)
        ON DELETE CASCADE
);
