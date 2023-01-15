CREATE DATABASE IF NOT EXISTS awb;
USE awb;
CREATE TABLE IF NOT EXISTS subreddits (
    name VARCHAR(20) PRIMARY KEY,
    settings JSON DEFAULT NULL,
    latest_utc INT DEFAULT NULL,
    revision_utc INT DEFAULT NULL
);
CREATE TABLE IF NOT EXISTS submissions (
    id VARCHAR(20) PRIMARY KEY,
    subreddit VARCHAR(20) NOT NULL,
    author VARCHAR(20) NOT NULL,
    created_utc INT NOT NULL,
    removed BOOL NOT NULL DEFAULT FALSE,
    deleted BOOL NOT NULL DEFAULT FALSE,
    approved BOOL NOT NULL DEFAULT FALSE,
    moderated BOOL NOT NULL DEFAULT FALSE,
    FOREIGN KEY (subreddit) REFERENCES subreddits(name) on DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS images (
    id INT AUTO_INCREMENT PRIMARY KEY,
    submission_id VARCHAR(20) NOT NULL,
    url VARCHAR(255) NOT NULL,
    width INT NOT NULL,
    height INT NOT NULL,
    UNIQUE KEY (submission_id, url),
    FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE
);
