-- PsychEngine schema. Spec §8.1. Idempotent.

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS books (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  author TEXT,
  cluster TEXT NOT NULL,
  file_path TEXT NOT NULL UNIQUE,
  total_chunks INTEGER DEFAULT 0,
  added_date TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  chapter_name TEXT,
  chunk_index INTEGER NOT NULL,
  text TEXT NOT NULL,
  page_start INTEGER,
  page_end INTEGER,
  token_estimate INTEGER
);
CREATE INDEX IF NOT EXISTS idx_chunks_book ON chunks(book_id);
CREATE INDEX IF NOT EXISTS idx_chunks_chapter ON chunks(book_id, chapter_name);

-- FTS5 virtual table for full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  text, chapter_name, content='chunks', content_rowid='id', tokenize='porter'
);
CREATE TRIGGER IF NOT EXISTS chunks_fts_ai AFTER INSERT ON chunks BEGIN
  INSERT INTO chunks_fts(rowid, text, chapter_name) VALUES (new.id, new.text, new.chapter_name);
END;
CREATE TRIGGER IF NOT EXISTS chunks_fts_ad AFTER DELETE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, text, chapter_name) VALUES('delete', old.id, old.text, old.chapter_name);
END;
CREATE TRIGGER IF NOT EXISTS chunks_fts_au AFTER UPDATE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, text, chapter_name) VALUES('delete', old.id, old.text, old.chapter_name);
  INSERT INTO chunks_fts(rowid, text, chapter_name) VALUES (new.id, new.text, new.chapter_name);
END;

CREATE TABLE IF NOT EXISTS topics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  visual_anchor_path TEXT,
  dependency_ids TEXT DEFAULT '[]',
  parent_topic_id INTEGER REFERENCES topics(id) ON DELETE SET NULL,
  cluster_hint TEXT,
  user_reviewed INTEGER DEFAULT 0,
  created_date TEXT DEFAULT (datetime('now')),
  modified_date TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chunk_topics (
  chunk_id INTEGER NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
  topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
  relevance_score REAL DEFAULT 0.5,
  PRIMARY KEY (chunk_id, topic_id)
);
CREATE INDEX IF NOT EXISTS idx_chunk_topics_topic ON chunk_topics(topic_id);

CREATE TABLE IF NOT EXISTS concept_extraction_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chunk_id INTEGER NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
  raw_concepts TEXT NOT NULL,
  gist TEXT,
  mapped_topic_ids TEXT DEFAULT '[]',
  ai_engine_used TEXT,
  processed_date TEXT DEFAULT (datetime('now')),
  user_reviewed INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_extraction_chunk ON concept_extraction_log(chunk_id);

CREATE TABLE IF NOT EXISTS user_progress (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  topic_id INTEGER NOT NULL UNIQUE REFERENCES topics(id) ON DELETE CASCADE,
  current_layer INTEGER DEFAULT 0,
  layer_1_date TEXT,
  layer_2_date TEXT,
  layer_3_date TEXT,
  layer_4_date TEXT,
  layer_5_date TEXT,
  next_layer_due TEXT,
  mastery_score REAL DEFAULT 0,
  status TEXT DEFAULT 'not_started'
);

CREATE TABLE IF NOT EXISTS quiz_results (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
  layer INTEGER,
  question_type TEXT,
  question_text TEXT,
  user_answer TEXT,
  correct_answer TEXT,
  is_correct INTEGER,
  timestamp TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS flashcards (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
  chunk_id INTEGER REFERENCES chunks(id) ON DELETE SET NULL,
  front TEXT NOT NULL,
  back TEXT NOT NULL,
  next_review_date TEXT,
  interval_days REAL DEFAULT 1,
  ease_factor REAL DEFAULT 2.5,
  review_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS highlights (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chunk_id INTEGER REFERENCES chunks(id) ON DELETE CASCADE,
  topic_id INTEGER REFERENCES topics(id) ON DELETE SET NULL,
  highlighted_text TEXT NOT NULL,
  user_note TEXT,
  color TEXT DEFAULT 'yellow',
  timestamp TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS field_reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT DEFAULT (datetime('now')),
  context TEXT,
  description TEXT,
  tactics_observed TEXT DEFAULT '[]',
  what_worked TEXT,
  what_failed TEXT,
  ai_feedback TEXT
);

CREATE TABLE IF NOT EXISTS personal_examples (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
  layer INTEGER,
  user_text TEXT,
  timestamp TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS mental_model_cards (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  topic_id INTEGER UNIQUE REFERENCES topics(id) ON DELETE CASCADE,
  key_points TEXT,
  when_used TEXT,
  when_fails TEXT,
  primary_counter TEXT,
  user_created_date TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS susceptibility_map (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  topic_id INTEGER UNIQUE REFERENCES topics(id) ON DELETE CASCADE,
  vulnerability_score REAL DEFAULT 50,
  last_assessed TEXT,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS reading_progress (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  book_id INTEGER REFERENCES books(id) ON DELETE CASCADE,
  chunk_id INTEGER REFERENCES chunks(id) ON DELETE CASCADE,
  read_in_linear_mode INTEGER DEFAULT 0,
  read_in_topic_mode INTEGER DEFAULT 0,
  read_date TEXT,
  UNIQUE(chunk_id)
);

CREATE TABLE IF NOT EXISTS daily_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT UNIQUE,
  planned_activities TEXT,
  completed_activities TEXT DEFAULT '[]',
  morning_recall_score REAL,
  session_duration_minutes REAL,
  completed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS streak_data (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT UNIQUE,
  session_completed INTEGER DEFAULT 0,
  current_streak INTEGER DEFAULT 0,
  longest_streak INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS simulator_personas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  personality_description TEXT,
  context_type TEXT,
  tactic_ids TEXT DEFAULT '[]',
  difficulty_level TEXT,
  source_chunks TEXT DEFAULT '[]',
  times_used INTEGER DEFAULT 0,
  avg_user_score REAL,
  last_used_date TEXT,
  is_effective INTEGER DEFAULT 0,
  created_date TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS simulator_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  persona_id INTEGER REFERENCES simulator_personas(id) ON DELETE SET NULL,
  topic_id INTEGER REFERENCES topics(id) ON DELETE SET NULL,
  layer INTEGER,
  conversation_log TEXT,
  tactics_used TEXT,
  tactics_caught TEXT,
  tactics_missed TEXT,
  score REAL,
  debrief_text TEXT,
  timestamp TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS topic_engagement_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
  engagement_type TEXT,
  score REAL,
  duration_seconds INTEGER,
  timestamp TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_engagement_topic ON topic_engagement_log(topic_id, timestamp);

CREATE TABLE IF NOT EXISTS topic_decay_state (
  topic_id INTEGER PRIMARY KEY REFERENCES topics(id) ON DELETE CASCADE,
  last_engaged_date TEXT,
  days_since_engagement INTEGER,
  estimated_retention REAL,
  decay_status TEXT,
  retention_history TEXT DEFAULT '[]',
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ai_cache (
  cache_key TEXT PRIMARY KEY,
  feature TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  response TEXT NOT NULL,
  engine_used TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_ai_cache_feature ON ai_cache(feature);

CREATE TABLE IF NOT EXISTS ai_api_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  feature TEXT,
  engine TEXT,
  key_index INTEGER,
  prompt_tokens INTEGER,
  completion_tokens INTEGER,
  duration_ms INTEGER,
  status TEXT,
  error TEXT,
  timestamp TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT
);
INSERT OR IGNORE INTO settings(key, value) VALUES
  ('session_minutes', '45'),
  ('new_topic_interval_days', '3'),
  ('ai_preference', 'auto'),
  ('theme', 'dark');
