-- Run once manually via `python migrations/init_db.py`

-- Guild configuration
CREATE TABLE IF NOT EXISTS guild_config (
    guild_id BIGINT PRIMARY KEY,
    approval_channel_id BIGINT,
    recruitment_channel_id BIGINT,
    progress_channel_id BIGINT,
    invoice_channel_id BIGINT,
    demolition_channel_id BIGINT,
    eviction_channel_id BIGINT,
    scroll_channel_id BIGINT,
    community_guild_id BIGINT,
    player_role_id BIGINT
);

-- Internal staff roles
CREATE TABLE IF NOT EXISTS user_roles (
    user_id BIGINT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'comayor', 'builder', 'recruiter')),
    granted_by BIGINT,
    granted_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, role)
);

CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(user_id);

-- Staff member profiles and reputation
CREATE TABLE IF NOT EXISTS staff_member (
    discord_id BIGINT PRIMARY KEY,
    display_name TEXT,
    reputation INTEGER DEFAULT 0
);

-- Recruitment form
CREATE TABLE IF NOT EXISTS recruitment (
    id SERIAL PRIMARY KEY,
    submitted_by BIGINT REFERENCES staff_member(discord_id),
    submitted_at TIMESTAMP DEFAULT NOW(),
    ingame_username TEXT NOT NULL,
    discord_username TEXT,
    age TEXT,
    nickname TEXT NOT NULL,
    recruiter_display TEXT,
    plots INTEGER DEFAULT 2,
    screenshot_urls TEXT,
    status TEXT DEFAULT 'pending',
    approved_by BIGINT,
    approved_at TIMESTAMP,
    thread_message_id BIGINT,
    approval_message_id BIGINT
);

-- Progress report form
CREATE TABLE IF NOT EXISTS progress_report (
    id SERIAL PRIMARY KEY,
    submitted_by BIGINT REFERENCES staff_member(discord_id),
    submitted_at TIMESTAMP DEFAULT NOW(),
    helper_mentions TEXT,
    project_name TEXT NOT NULL,
    time_spent TEXT NOT NULL,
    screenshot_urls TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    approved_by BIGINT,
    approved_at TIMESTAMP,
    thread_message_id BIGINT,
    approval_message_id BIGINT
);

-- Purchase invoice form
CREATE TABLE IF NOT EXISTS purchase_invoice (
    id SERIAL PRIMARY KEY,
    submitted_by BIGINT REFERENCES staff_member(discord_id),
    submitted_at TIMESTAMP DEFAULT NOW(),
    seller_display TEXT,
    purchasee_nickname TEXT NOT NULL,
    purchasee_ingame TEXT NOT NULL,
    purchase_type TEXT NOT NULL,
    num_plots INTEGER,
    total_plots INTEGER,
    banner_color TEXT,
    shop_number INTEGER,
    amount_deposited NUMERIC,
    screenshot_urls TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    approved_by BIGINT,
    approved_at TIMESTAMP,
    thread_message_id BIGINT,
    approval_message_id BIGINT
);

-- Demolition report
CREATE TABLE IF NOT EXISTS demolition_report (
    id SERIAL PRIMARY KEY,
    submitted_by BIGINT REFERENCES staff_member(discord_id),
    submitted_at TIMESTAMP DEFAULT NOW(),
    ingame_username TEXT NOT NULL,
    removed TEXT NOT NULL,
    stashed_items BOOLEAN NOT NULL,
    screenshot_urls TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    approved_by BIGINT,
    approved_at TIMESTAMP,
    thread_message_id BIGINT,
    approval_message_id BIGINT
);

-- Admin demolition request
CREATE TABLE IF NOT EXISTS demolition_request (
    id SERIAL PRIMARY KEY,
    submitted_by BIGINT REFERENCES staff_member(discord_id),
    submitted_at TIMESTAMP DEFAULT NOW(),
    ingame_username TEXT NOT NULL,
    reason TEXT NOT NULL,
    screenshot_urls TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    approved_by BIGINT,
    approved_at TIMESTAMP,
    thread_message_id BIGINT,
    approval_message_id BIGINT
);

-- Eviction report
CREATE TABLE IF NOT EXISTS eviction_report (
    id SERIAL PRIMARY KEY,
    submitted_by BIGINT REFERENCES staff_member(discord_id),
    submitted_at TIMESTAMP DEFAULT NOW(),
    ingame_owner TEXT NOT NULL,
    items_stored BOOLEAN NOT NULL,
    inactivity_period TEXT NOT NULL,
    screenshot_urls TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    approved_by BIGINT,
    approved_at TIMESTAMP,
    thread_message_id BIGINT,
    approval_message_id BIGINT
);

-- Scroll completion report
CREATE TABLE IF NOT EXISTS scroll_completion (
    id SERIAL PRIMARY KEY,
    submitted_by BIGINT REFERENCES staff_member(discord_id),
    submitted_at TIMESTAMP DEFAULT NOW(),
    scroll_type TEXT NOT NULL,
    items_stored BOOLEAN NOT NULL,
    screenshot_urls TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    approved_by BIGINT,
    approved_at TIMESTAMP,
    thread_message_id BIGINT,
    approval_message_id BIGINT
);

-- Reputation log
CREATE TABLE IF NOT EXISTS reputation_log (
    id SERIAL PRIMARY KEY,
    staff_id BIGINT REFERENCES staff_member(discord_id),
    points INT NOT NULL,
    reason TEXT,
    form_type TEXT,
    form_id INT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Leaderboard views
CREATE OR REPLACE VIEW weekly_reputation AS
SELECT staff_id, SUM(points) AS points
FROM reputation_log
WHERE created_at >= date_trunc('week', CURRENT_DATE)
GROUP BY staff_id;

CREATE OR REPLACE VIEW biweekly_reputation AS
SELECT staff_id, SUM(points) AS points
FROM reputation_log
WHERE created_at >= date_trunc('week', CURRENT_DATE) - INTERVAL '1 week'
GROUP BY staff_id;

CREATE OR REPLACE VIEW monthly_reputation AS
SELECT staff_id, SUM(points) AS points
FROM reputation_log
WHERE created_at >= date_trunc('month', CURRENT_DATE)
GROUP BY staff_id;