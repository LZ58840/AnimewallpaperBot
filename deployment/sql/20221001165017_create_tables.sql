USE animewallpaper;

CREATE TABLE IF NOT EXISTS subreddit (
    name VARCHAR(20) PRIMARY KEY ,
    updated INT
);

CREATE TABLE IF NOT EXISTS submission (
    id VARCHAR(10) PRIMARY KEY ,
    url VARCHAR(512) NOT NULL ,
    subreddit VARCHAR(20) NOT NULL ,
    author VARCHAR(20) NOT NULL ,
    created INT NOT NULL ,
    removed TINYINT NOT NULL DEFAULT 0 ,
    extracted TINYINT NOT NULL DEFAULT 0,

    FOREIGN KEY (subreddit)
        REFERENCES subreddit(name)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS image_metadata (
    id INT AUTO_INCREMENT PRIMARY KEY ,
    url VARCHAR(255) NOT NULL ,
    submission_id VARCHAR(10) NOT NULL ,
    encoded TINYINT NOT NULL DEFAULT 0,

    UNIQUE KEY (url, submission_id),

    FOREIGN KEY (submission_id)
        REFERENCES submission(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS image_data (
    id INT PRIMARY KEY ,
    width INT NOT NULL ,
    height INT NOT NULL ,
    4histogram_red_1 INT NOT NULL ,
    4histogram_red_2 INT NOT NULL ,
    4histogram_red_3 INT NOT NULL ,
    4histogram_red_4 INT NOT NULL ,
    4histogram_green_1 INT NOT NULL ,
    4histogram_green_2 INT NOT NULL ,
    4histogram_green_3 INT NOT NULL ,
    4histogram_green_4 INT NOT NULL ,
    4histogram_blue_1 INT NOT NULL ,
    4histogram_blue_2 INT NOT NULL ,
    4histogram_blue_3 INT NOT NULL ,
    4histogram_blue_4 INT NOT NULL ,
    dhash_red BIT(64) NOT NULL ,
    dhash_green BIT(64) NOT NULL ,
    dhash_blue BIT(64) NOT NULL ,

    FOREIGN KEY (id)
        REFERENCES image_metadata(id)
        ON DELETE CASCADE
);
