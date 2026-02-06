-- Subhamasthu Database Migration v2
-- Adds fields for Sankalp eligibility tracking

-- Add onboarded_at to track when user completed onboarding
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS onboarded_at TIMESTAMPTZ;

-- Add rashiphalalu_days_sent to track 6-day eligibility
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS rashiphalalu_days_sent INTEGER DEFAULT 0 NOT NULL;

-- Add index for quick eligibility lookups
CREATE INDEX IF NOT EXISTS idx_users_rashiphalalu_days ON users(rashiphalalu_days_sent);
