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
    extracted INT NOT NULL DEFAULT 0,
    updated_at INT ,

    FOREIGN KEY (subreddit)
        REFERENCES subreddit(name)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS image (
    id INT AUTO_INCREMENT PRIMARY KEY ,
    url VARCHAR(255) NOT NULL ,
    submission_id VARCHAR(10) NOT NULL ,
    encoded INT NOT NULL DEFAULT 0 ,
    updated_at INT ,
    width INT NOT NULL DEFAULT -1,
    height INT NOT NULL DEFAULT -1,

    UNIQUE KEY (url, submission_id),

    FOREIGN KEY (submission_id)
        REFERENCES submission(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS 4histogram (
    id INT PRIMARY KEY ,
    red_1 INT NOT NULL ,
    red_2 INT NOT NULL ,
    red_3 INT NOT NULL ,
    red_4 INT NOT NULL ,
    green_1 INT NOT NULL ,
    green_2 INT NOT NULL ,
    green_3 INT NOT NULL ,
    green_4 INT NOT NULL ,
    blue_1 INT NOT NULL ,
    blue_2 INT NOT NULL ,
    blue_3 INT NOT NULL ,
    blue_4 INT NOT NULL ,

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
