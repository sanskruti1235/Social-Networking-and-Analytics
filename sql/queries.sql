-- =====================================================================
-- queries.sql - 26 queries. The Streamlit "Query lab" reads this file,
-- so keep each header in the form:   -- #N | Title | Concept
-- Run migration.sql first (queries 17, 22, 26 use views / activity_log).
-- =====================================================================

-- #1 | Posts from chosen places | SELECT, WHERE, LIKE, ORDER BY
SELECT post_id, user_id, caption, location
FROM post
WHERE location LIKE '%Agra%' OR location LIKE '%Delhi%' OR location LIKE '%Ladakh%'
ORDER BY post_id;

-- #2 | Most followed hashtags | INNER JOIN, COUNT, GROUP BY, LIMIT
SELECT TRIM(h.hashtag_name) AS hashtag, COUNT(*) AS followers
FROM hashtag_follow hf
INNER JOIN hashtags h ON h.hashtag_id = hf.hashtag_id
GROUP BY h.hashtag_id, h.hashtag_name
ORDER BY followers DESC
LIMIT 5;

-- #3 | Most used hashtags | INNER JOIN, COUNT, GROUP BY
SELECT TRIM(h.hashtag_name) AS hashtag, COUNT(*) AS times_used
FROM post_tags pt
INNER JOIN hashtags h ON h.hashtag_id = pt.hashtag_id
GROUP BY h.hashtag_id, h.hashtag_name
ORDER BY times_used DESC
LIMIT 10;

-- #4 | Users who never posted | LEFT JOIN + IS NULL (anti-join)
SELECT u.user_id, u.username
FROM users u
LEFT JOIN post p ON p.user_id = u.user_id
WHERE p.post_id IS NULL;

-- #5 | Most liked posts | INNER + LEFT JOIN, COUNT, GROUP BY
SELECT p.post_id, u.username, p.caption, COUNT(pl.user_id) AS likes
FROM post p
INNER JOIN users u ON u.user_id = p.user_id
LEFT JOIN post_likes pl ON pl.post_id = p.post_id
GROUP BY p.post_id, u.username, p.caption
ORDER BY likes DESC, p.post_id
LIMIT 10;

-- #6 | Posts per user: average, fewest, most | AVG, MIN, MAX, derived table
SELECT ROUND(AVG(post_count), 2) AS avg_posts_per_user,
       MIN(post_count) AS fewest, MAX(post_count) AS most
FROM (SELECT user_id, COUNT(*) AS post_count FROM post GROUP BY user_id) AS t;

-- #7 | Logins per user | LEFT JOIN, COUNT, MAX
SELECT u.user_id, u.username, COUNT(l.login_id) AS logins, MAX(l.login_time) AS last_login
FROM users u
LEFT JOIN login l ON l.user_id = u.user_id
GROUP BY u.user_id, u.username
ORDER BY logins DESC, u.user_id
LIMIT 20;

-- #8 | Liked every single post (bot check) | HAVING + scalar subquery
SELECT u.username, COUNT(*) AS posts_liked
FROM users u
INNER JOIN post_likes pl ON pl.user_id = u.user_id
GROUP BY u.user_id, u.username
HAVING COUNT(*) = (SELECT COUNT(*) FROM post);

-- #9 | Users who never commented | LEFT JOIN + IS NULL
SELECT u.user_id, u.username
FROM users u
LEFT JOIN comments c ON c.user_id = u.user_id
WHERE c.comment_id IS NULL;

-- #10 | Commented on every post (bot check) | COUNT DISTINCT, HAVING
SELECT u.username, COUNT(DISTINCT c.post_id) AS posts_commented
FROM users u
INNER JOIN comments c ON c.user_id = u.user_id
GROUP BY u.user_id, u.username
HAVING COUNT(DISTINCT c.post_id) = (SELECT COUNT(*) FROM post);

-- #11 | Users nobody follows | LEFT JOIN + IS NULL
SELECT u.user_id, u.username
FROM users u
LEFT JOIN follows f ON f.followee_id = u.user_id
WHERE f.follower_id IS NULL;

-- #12 | Users who follow nobody | LEFT JOIN + IS NULL
SELECT u.user_id, u.username
FROM users u
LEFT JOIN follows f ON f.follower_id = u.user_id
WHERE f.followee_id IS NULL;

-- #13 | Users with more than 5 posts | GROUP BY, HAVING
SELECT u.username, COUNT(*) AS post_count
FROM post p
INNER JOIN users u ON u.user_id = p.user_id
GROUP BY u.user_id, u.username
HAVING COUNT(*) > 5
ORDER BY post_count DESC;

-- #14 | Users with more than 40 followers | GROUP BY, HAVING
SELECT u.username, COUNT(*) AS follower_count
FROM follows f
INNER JOIN users u ON u.user_id = f.followee_id
GROUP BY u.user_id, u.username
HAVING COUNT(*) > 40
ORDER BY follower_count DESC;

-- #15 | Comments containing certain words | REGEXP
SELECT u.username, c.comment_text
FROM comments c
INNER JOIN users u ON u.user_id = c.user_id
WHERE c.comment_text REGEXP 'good|beautiful'
LIMIT 50;

-- #16 | Longest captions | LENGTH, ORDER BY, LIMIT
SELECT u.username, p.caption, LENGTH(p.caption) AS caption_length
FROM post p
INNER JOIN users u ON u.user_id = p.user_id
ORDER BY caption_length DESC
LIMIT 5;

-- #17 | Engagement per creator | SUM, AVG, MIN, MAX over a view
SELECT u.username, SUM(e.likes) AS total_likes, COUNT(*) AS posts,
       ROUND(AVG(e.likes), 1) AS avg_likes, MIN(e.likes) AS min_likes,
       MAX(e.likes) AS max_likes, SUM(e.comments) AS total_comments
FROM vw_post_engagement e
INNER JOIN users u ON u.user_id = e.user_id
GROUP BY u.user_id, u.username
HAVING SUM(e.likes) > 0
ORDER BY total_likes DESC
LIMIT 10;

-- #18 | Bookmarks per user, including users with none | RIGHT JOIN
SELECT u.username, COUNT(b.post_id) AS bookmarks
FROM bookmarks b
RIGHT JOIN users u ON u.user_id = b.user_id
GROUP BY u.user_id, u.username
ORDER BY bookmarks DESC, u.username
LIMIT 15;

-- #19 | Mutual followers (friends) | Self-join on follows
SELECT a.username AS person_a, b.username AS person_b
FROM follows f1
INNER JOIN follows f2 ON f2.follower_id = f1.followee_id AND f2.followee_id = f1.follower_id
INNER JOIN users a ON a.user_id = f1.follower_id
INNER JOIN users b ON b.user_id = f1.followee_id
WHERE f1.follower_id < f1.followee_id
ORDER BY a.username
LIMIT 25;

-- #20 | Who should user 1 follow? (friends of friends) | Self-join, NOT IN, GROUP BY
SELECT u.username, COUNT(*) AS mutual_connections
FROM follows f1
INNER JOIN follows f2 ON f2.follower_id = f1.followee_id
INNER JOIN users u ON u.user_id = f2.followee_id
WHERE f1.follower_id = 1
  AND f2.followee_id <> 1
  AND f2.followee_id NOT IN (SELECT followee_id FROM follows WHERE follower_id = 1)
GROUP BY u.user_id, u.username
ORDER BY mutual_connections DESC
LIMIT 10;

-- #21 | Posts per month | DATE_FORMAT, GROUP BY
SELECT DATE_FORMAT(created_at, '%Y-%m') AS month, COUNT(*) AS posts
FROM post
GROUP BY DATE_FORMAT(created_at, '%Y-%m')
ORDER BY month;

-- #22 | Follower leaderboard | Window function RANK() over a view
SELECT username, followers, RANK() OVER (ORDER BY followers DESC) AS follower_rank
FROM vw_user_stats
ORDER BY follower_rank, username
LIMIT 10;

-- #23 | Posts with above-average likes | CTE + subquery
WITH like_counts AS (
    SELECT post_id, COUNT(*) AS likes FROM post_likes GROUP BY post_id
)
SELECT p.post_id, p.caption, lc.likes
FROM post p
INNER JOIN like_counts lc ON lc.post_id = p.post_id
WHERE lc.likes > (SELECT AVG(likes) FROM like_counts)
ORDER BY lc.likes DESC
LIMIT 15;

-- #24 | Hashtags people follow but nobody has used | LEFT JOIN + IS NULL
SELECT TRIM(h.hashtag_name) AS hashtag, COUNT(DISTINCT hf.user_id) AS followers
FROM hashtags h
INNER JOIN hashtag_follow hf ON hf.hashtag_id = h.hashtag_id
LEFT JOIN post_tags pt ON pt.hashtag_id = h.hashtag_id
WHERE pt.post_id IS NULL
GROUP BY h.hashtag_id, h.hashtag_name
ORDER BY followers DESC;

-- #25 | Busiest login hours | HOUR(), GROUP BY
SELECT HOUR(login_time) AS hour_of_day, COUNT(*) AS logins
FROM login
GROUP BY HOUR(login_time)
ORDER BY hour_of_day;

-- #26 | What happened in the app (trigger log) | GROUP BY on trigger-filled table
SELECT action, COUNT(*) AS times
FROM activity_log
GROUP BY action
ORDER BY times DESC;