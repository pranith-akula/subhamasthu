-- Migration: Add seva_medias table for Annadanam proof
-- Pooled footage model for trust-building

CREATE TABLE IF NOT EXISTS seva_medias (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Media info
    media_type VARCHAR(10) NOT NULL DEFAULT 'image',  -- 'image' or 'video'
    cloudinary_url VARCHAR(500) NOT NULL,
    cloudinary_public_id VARCHAR(200),
    
    -- Optional metadata (falls back to random Hyderabad temple if null)
    temple_name VARCHAR(200),
    location VARCHAR(200),
    
    -- Seva info
    seva_date DATE,
    seva_time TIME,
    families_fed INTEGER,
    
    -- Tracking
    used_count INTEGER DEFAULT 0,
    caption TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for efficient random selection by usage
CREATE INDEX IF NOT EXISTS idx_seva_medias_used_count ON seva_medias(used_count);

-- Add proof_sent flag to sankalpas
ALTER TABLE sankalpas ADD COLUMN IF NOT EXISTS proof_sent BOOLEAN DEFAULT FALSE;
ALTER TABLE sankalpas ADD COLUMN IF NOT EXISTS proof_sent_at TIMESTAMP;
