-- =====================================================================
-- migration.sql  -  run ONCE in MySQL Workbench, AFTER schema.sql and
-- table_database.sql. Adds login support, views, indexes and triggers.
-- =====================================================================
USE social_media;

-- 1. Login support ----------------------------------------------------
ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) NULL;
ALTER TABLE users MODIFY email VARCHAR(100) NOT NULL;   -- 30 chars was too short

-- every seeded user gets the demo password  chowk123  (salted SHA-256)
UPDATE users
SET password_hash = CONCAT('demo$', SHA2(CONCAT('demo', 'chowk123'), 256))
WHERE password_hash IS NULL AND user_id > 0;

-- 2. Indexes ----------------------------------------------------------
CREATE INDEX idx_post_created ON post(created_at);
CREATE INDEX idx_login_time   ON login(login_time);

-- 3. Views ------------------------------------------------------------
CREATE OR REPLACE VIEW vw_user_stats AS
SELECT u.user_id, u.username,
       (SELECT COUNT(*) FROM post   p WHERE p.user_id     = u.user_id) AS posts,
       (SELECT COUNT(*) FROM follows f WHERE f.followee_id = u.user_id) AS followers,
       (SELECT COUNT(*) FROM follows f WHERE f.follower_id = u.user_id) AS following
FROM users u;

CREATE OR REPLACE VIEW vw_post_engagement AS
SELECT p.post_id, p.user_id, p.caption,
       (SELECT COUNT(*) FROM post_likes l WHERE l.post_id = p.post_id) AS likes,
       (SELECT COUNT(*) FROM comments   c WHERE c.post_id = p.post_id) AS comments,
       (SELECT COUNT(*) FROM bookmarks  b WHERE b.post_id = p.post_id) AS saves
FROM post p;

-- 4. Activity log + triggers (every app action leaves a trace) ---------
CREATE TABLE IF NOT EXISTS activity_log (
    log_id     INTEGER AUTO_INCREMENT PRIMARY KEY,
    user_id    INTEGER,
    action     VARCHAR(20) NOT NULL,
    target_id  INTEGER,
    details    VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_user_registered;
CREATE TRIGGER trg_user_registered AFTER INSERT ON users FOR EACH ROW
  INSERT INTO activity_log(user_id, action, target_id, details)
  VALUES (NEW.user_id, 'REGISTER', NEW.user_id, NEW.username);

DROP TRIGGER IF EXISTS trg_login;
CREATE TRIGGER trg_login AFTER INSERT ON login FOR EACH ROW
  INSERT INTO activity_log(user_id, action, target_id, details)
  VALUES (NEW.user_id, 'LOGIN', NEW.login_id, NEW.ip);

DROP TRIGGER IF EXISTS trg_post_created;
CREATE TRIGGER trg_post_created AFTER INSERT ON post FOR EACH ROW
  INSERT INTO activity_log(user_id, action, target_id, details)
  VALUES (NEW.user_id, 'POST', NEW.post_id, LEFT(NEW.caption, 100));

DROP TRIGGER IF EXISTS trg_comment_created;
CREATE TRIGGER trg_comment_created AFTER INSERT ON comments FOR EACH ROW
  INSERT INTO activity_log(user_id, action, target_id, details)
  VALUES (NEW.user_id, 'COMMENT', NEW.post_id, LEFT(NEW.comment_text, 100));

DROP TRIGGER IF EXISTS trg_like_added;
CREATE TRIGGER trg_like_added AFTER INSERT ON post_likes FOR EACH ROW
  INSERT INTO activity_log(user_id, action, target_id, details)
  VALUES (NEW.user_id, 'LIKE', NEW.post_id, CONCAT('liked post #', NEW.post_id));

DROP TRIGGER IF EXISTS trg_like_removed;
CREATE TRIGGER trg_like_removed AFTER DELETE ON post_likes FOR EACH ROW
  INSERT INTO activity_log(user_id, action, target_id, details)
  VALUES (OLD.user_id, 'UNLIKE', OLD.post_id, CONCAT('unliked post #', OLD.post_id));

DROP TRIGGER IF EXISTS trg_follow_added;
CREATE TRIGGER trg_follow_added AFTER INSERT ON follows FOR EACH ROW
  INSERT INTO activity_log(user_id, action, target_id, details)
  VALUES (NEW.follower_id, 'FOLLOW', NEW.followee_id, CONCAT('followed user #', NEW.followee_id));

DROP TRIGGER IF EXISTS trg_follow_removed;
CREATE TRIGGER trg_follow_removed AFTER DELETE ON follows FOR EACH ROW
  INSERT INTO activity_log(user_id, action, target_id, details)
  VALUES (OLD.follower_id, 'UNFOLLOW', OLD.followee_id, CONCAT('unfollowed user #', OLD.followee_id));