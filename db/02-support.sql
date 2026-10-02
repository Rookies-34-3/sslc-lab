CREATE TABLE IF NOT EXISTS user_profiles (
    user_id INT UNSIGNED PRIMARY KEY,
    email VARCHAR(254) NOT NULL DEFAULT '',
    phone VARCHAR(20) NOT NULL DEFAULT '',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB;

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

SET @inquiry_privacy_sql = IF(
    EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='inquiries' AND column_name='is_secret'),
    'DO 0',
    'ALTER TABLE inquiries ADD COLUMN is_secret BOOLEAN NOT NULL DEFAULT TRUE AFTER body'
);
PREPARE inquiry_privacy_stmt FROM @inquiry_privacy_sql;
EXECUTE inquiry_privacy_stmt;
DEALLOCATE PREPARE inquiry_privacy_stmt;
