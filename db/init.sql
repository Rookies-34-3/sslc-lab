-- 유저 테이블
CREATE TABLE users (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    display_name VARCHAR(80) NOT NULL,
    role ENUM('student', 'admin') NOT NULL DEFAULT 'student',
    password_hash VARCHAR(255) NOT NULL
) ENGINE=InnoDB;

-- 게시판
CREATE TABLE posts (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    kind ENUM('notice', 'qna') NOT NULL,
    author_id INT UNSIGNED NOT NULL,
    title VARCHAR(200) NOT NULL,
    body TEXT NOT NULL,
    views INT UNSIGNED NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (author_id) REFERENCES users(id),
    INDEX board_order (kind, created_at, id)
) ENGINE=InnoDB;

-- PBL file 테이블
CREATE TABLE files (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    owner_id INT UNSIGNED NOT NULL,
    post_id INT UNSIGNED NULL,
    problem_id INT UNSIGNED NULL,
    original_name VARCHAR(180) NOT NULL,
    stored_name VARCHAR(80) NOT NULL UNIQUE,
    size_bytes INT UNSIGNED NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id),
    FOREIGN KEY (post_id) REFERENCES posts(id),
    CHECK ((post_id IS NULL) <> (problem_id IS NULL)),
    INDEX submissions (owner_id, problem_id)
) ENGINE=InnoDB;

REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'sslc_app'@'%';
GRANT SELECT, INSERT, UPDATE ON sslc_lab.* TO 'sslc_app'@'%';
