USE animewallpaper;

CREATE TABLE IF NOT EXISTS subreddit (
    name VARCHAR(20) PRIMARY KEY ,
    updated INT
);

CREATE TABLE IF NOT EXISTS submission (
    id VARCHAR(10) PRIMARY KEY ,
    subreddit VARCHAR(20) NOT NULL ,
    author VARCHAR(20) NOT NULL ,
    created INT NOT NULL ,
    removed INT NOT NULL DEFAULT 0 ,

    FOREIGN KEY (subreddit)
        REFERENCES subreddit(name)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS link (
    id VARCHAR(10) PRIMARY KEY ,
    url VARCHAR(255) NOT NULL ,
    type VARCHAR(255) ,
    created INT NOT NULL ,
    last_visited INT ,
    priority INT NOT NULL DEFAULT 0 ,

    FOREIGN KEY (id)
        REFERENCES submission(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS image (
    id INT AUTO_INCREMENT PRIMARY KEY ,
    url VARCHAR(255) NOT NULL ,
    submission_id VARCHAR(10) NOT NULL ,
    width INT NOT NULL ,
    height INT NOT NULL ,

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
