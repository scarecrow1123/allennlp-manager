DROP TABLE IF EXISTS user;

CREATE TABLE user (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  alt_id INTEGER NOT NULL,
  username TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL
);