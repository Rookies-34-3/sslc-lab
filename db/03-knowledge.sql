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
