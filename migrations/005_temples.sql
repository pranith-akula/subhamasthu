-- Migration: Add temples table and link to seva_medias/sankalps
-- Multi-Temple Metadata for Annadanam proof

CREATE TABLE IF NOT EXISTS temples (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Temple info
    name VARCHAR(200) NOT NULL,
    name_telugu VARCHAR(200),
    location VARCHAR(200),
    city VARCHAR(100) DEFAULT 'Hyderabad',
    
    -- Religious info
    deity VARCHAR(100),
    
    -- Media
    photo_url VARCHAR(500),
    google_maps_url VARCHAR(500),
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for efficient lookups
CREATE INDEX IF NOT EXISTS idx_temples_city ON temples(city);
CREATE INDEX IF NOT EXISTS idx_temples_deity ON temples(deity);
CREATE INDEX IF NOT EXISTS idx_temples_active ON temples(is_active);

-- Link seva_medias to temples (optional - for attributed photos)
ALTER TABLE seva_medias ADD COLUMN IF NOT EXISTS temple_id UUID REFERENCES temples(id);

-- Link sankalps to temples (optional - for tracking which temple served)
ALTER TABLE sankalps ADD COLUMN IF NOT EXISTS temple_id UUID REFERENCES temples(id);
