-- SSLC Lab 통합 스키마

-- 유저 테이블
CREATE TABLE IF NOT EXISTS users (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    display_name VARCHAR(80) NOT NULL,
    role ENUM('student', 'admin') NOT NULL DEFAULT 'student',
    password_hash VARCHAR(255) NOT NULL
) ENGINE=InnoDB;

-- 게시판
CREATE TABLE IF NOT EXISTS posts (
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
CREATE TABLE IF NOT EXISTS files (
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

-- 사용자 프로필
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id INT UNSIGNED PRIMARY KEY,
    email VARCHAR(254) NOT NULL DEFAULT '',
    phone VARCHAR(20) NOT NULL DEFAULT '',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB;

-- 문의하기
CREATE TABLE IF NOT EXISTS inquiries (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    owner_id INT UNSIGNED NOT NULL,
    category VARCHAR(30) NOT NULL DEFAULT '기타',
    title VARCHAR(200) NOT NULL,
    body TEXT NOT NULL,
    is_secret BOOLEAN NOT NULL DEFAULT TRUE,
    answer TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    answered_at DATETIME NULL,
    FOREIGN KEY (owner_id) REFERENCES users(id),
    INDEX owner_created (owner_id, created_at, id)
) ENGINE=InnoDB;

-- 기존 문의 테이블에 비밀글 컬럼이 없을 때만 추가
SET @inquiry_privacy_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='inquiries' AND column_name='is_secret'),
    'DO 0',
    'ALTER TABLE inquiries ADD COLUMN is_secret BOOLEAN NOT NULL DEFAULT TRUE AFTER body'
);
PREPARE inquiry_privacy_stmt FROM @inquiry_privacy_sql;
EXECUTE inquiry_privacy_stmt;
DEALLOCATE PREPARE inquiry_privacy_stmt;

-- 지식컨텐츠
CREATE TABLE IF NOT EXISTS external_contents (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    owner_id INT UNSIGNED NOT NULL,
    title VARCHAR(200) NOT NULL,
    source_url TEXT NOT NULL,
    thumbnail_path VARCHAR(160) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id),
    INDEX content_created (created_at, id)
) ENGINE=InnoDB;

-- 기존 앱 계정 권한 설정
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'sslc_app'@'%';
GRANT SELECT, INSERT, UPDATE ON sslc_lab.* TO 'sslc_app'@'%';
