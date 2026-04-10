-- Portfolio Coach feature schema
-- Run this in Supabase SQL Editor BEFORE deploying

-- 1. Submission history
CREATE TABLE IF NOT EXISTS portfolio_submissions (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      timestamptz NOT NULL DEFAULT now(),
    ip_hash         text NOT NULL,
    storage_path    text NOT NULL,
    file_size       int NOT NULL,
    page_count      int,
    image_count     int,
    image_truncated boolean DEFAULT false,
    model_used      text,
    used_byok       boolean DEFAULT false,
    used_fallback   boolean DEFAULT false,
    tokens_input    int,
    tokens_output   int,
    eval_summary    text,
    status          text NOT NULL DEFAULT 'pending',
    error           text
);

CREATE INDEX IF NOT EXISTS idx_portfolio_submissions_created
    ON portfolio_submissions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_portfolio_submissions_ip
    ON portfolio_submissions(ip_hash);

-- 2. Per-IP rate limit (KST daily window)
CREATE TABLE IF NOT EXISTS portfolio_ratelimit (
    ip_hash         text NOT NULL,
    window_date     date NOT NULL,
    count           int NOT NULL DEFAULT 0,
    updated_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (ip_hash, window_date)
);

-- 3. Global daily RPD counter
CREATE TABLE IF NOT EXISTS portfolio_daily_count (
    date            date PRIMARY KEY,
    count           int NOT NULL DEFAULT 0,
    cap             int NOT NULL DEFAULT 240
);

-- 4. Storage bucket creation
-- NOTE: Run via Supabase Dashboard → Storage → New bucket
--       name: portfolio-uploads
--       public: false
-- Or via SQL:
INSERT INTO storage.buckets (id, name, public)
VALUES ('portfolio-uploads', 'portfolio-uploads', false)
ON CONFLICT (id) DO NOTHING;

-- 5. User feedback
CREATE TABLE IF NOT EXISTS portfolio_feedback (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      timestamptz NOT NULL DEFAULT now(),
    ip_hash         text,
    message         text NOT NULL,
    image_path      text,
    status          text NOT NULL DEFAULT 'new'
);

CREATE INDEX IF NOT EXISTS idx_portfolio_feedback_created
    ON portfolio_feedback(created_at DESC);
