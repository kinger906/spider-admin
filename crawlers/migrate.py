#!/usr/bin/env python3
"""Create spider_ prefixed tables without touching existing tables."""

import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from framework.db import get_connection
from dotenv import load_dotenv
load_dotenv()

SCHEMA_SQL = """
DO $$ BEGIN
  CREATE TYPE spider_crawler_status AS ENUM ('idle','running','paused','error','disabled');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE spider_task_status AS ENUM ('pending','running','success','failed','cancelled');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS spider_crawlers (
  id SERIAL PRIMARY KEY,
  name VARCHAR(128) NOT NULL UNIQUE,
  slug VARCHAR(128) NOT NULL UNIQUE,
  description TEXT,
  file_path VARCHAR(512) NOT NULL,
  status spider_crawler_status NOT NULL DEFAULT 'idle',
  schedule VARCHAR(64),
  config JSONB DEFAULT '{}',
  retry_limit INTEGER NOT NULL DEFAULT 3,
  enabled BOOLEAN NOT NULL DEFAULT true,
  last_run_at TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS spider_tasks (
  id SERIAL PRIMARY KEY,
  crawler_id INTEGER NOT NULL REFERENCES spider_crawlers(id) ON DELETE CASCADE,
  status spider_task_status NOT NULL DEFAULT 'pending',
  triggered_by VARCHAR(32) NOT NULL DEFAULT 'manual',
  started_at TIMESTAMP,
  finished_at TIMESTAMP,
  items_count INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,
  retry_count INTEGER NOT NULL DEFAULT 0,
  logs TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS spider_data_records (
  id SERIAL PRIMARY KEY,
  crawler_id INTEGER NOT NULL REFERENCES spider_crawlers(id) ON DELETE CASCADE,
  task_id INTEGER REFERENCES spider_tasks(id) ON DELETE SET NULL,
  data JSONB NOT NULL,
  url TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS spider_media_files (
  id SERIAL PRIMARY KEY,
  crawler_id INTEGER NOT NULL REFERENCES spider_crawlers(id) ON DELETE CASCADE,
  task_id INTEGER REFERENCES spider_tasks(id) ON DELETE SET NULL,
  file_name VARCHAR(512) NOT NULL,
  blob_url TEXT NOT NULL,
  mime_type VARCHAR(128),
  size_bytes INTEGER,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS spider_system_logs (
  id SERIAL PRIMARY KEY,
  level VARCHAR(16) NOT NULL DEFAULT 'info',
  source VARCHAR(128),
  message TEXT NOT NULL,
  meta JSONB,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_spider_data_records_crawler_url ON spider_data_records(crawler_id, url);

CREATE TABLE IF NOT EXISTS spider_users (
  id SERIAL PRIMARY KEY,
  username VARCHAR(64) NOT NULL UNIQUE,
  password_hash VARCHAR(256) NOT NULL,
  display_name VARCHAR(128),
  role VARCHAR(32) NOT NULL DEFAULT 'admin',
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS spider_sessions (
  id VARCHAR(64) PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES spider_users(id) ON DELETE CASCADE,
  expires_at TIMESTAMP NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
"""

SEED_SQL = """
INSERT INTO spider_users (username, password_hash, display_name, role)
VALUES ('admin', 'admin123', 'Administrator', 'admin')
ON CONFLICT (username) DO NOTHING;
"""

if __name__ == "__main__":
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(SCHEMA_SQL)
        cur.execute(SEED_SQL)
    print("Migration complete: spider_ tables created, admin user seeded")
