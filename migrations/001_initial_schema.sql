-- Subhamasthu Database Schema
-- Neon Postgres Migration v1

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- ENUMS
-- =============================================================================

CREATE TYPE conversation_state AS ENUM (
    'NEW',
    'WAITING_FOR_RASHI',
    'WAITING_FOR_NAKSHATRA',
    'WAITING_FOR_BIRTH_TIME',
    'WAITING_FOR_DEITY',
    'WAITING_FOR_AUSPICIOUS_DAY',
    'ONBOARDED',
    'DAILY_PASSIVE',
    'WEEKLY_PROMPT_SENT',
    'WAITING_FOR_CATEGORY',
    'WAITING_FOR_TIER',
    'PAYMENT_LINK_SENT',
    'PAYMENT_CONFIRMED',
    'RECEIPT_SENT',
    'COOLDOWN'
);

CREATE TYPE sankalp_status AS ENUM (
    'INITIATED',
    'PAYMENT_PENDING',
    'PAID',
    'RECEIPT_SENT',
    'CLOSED'
);

CREATE TYPE transfer_status AS ENUM (
    'PENDING',
    'TRANSFERRED'
);

-- =============================================================================
-- USERS TABLE
-- =============================================================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(255),
    rashi VARCHAR(50),                              -- MANDATORY
    nakshatra VARCHAR(50),                          -- OPTIONAL: Janam Nakshatra
    birth_time VARCHAR(10),                         -- OPTIONAL: HH:MM format
    preferred_deity VARCHAR(50),
    auspicious_day VARCHAR(20),
    tz VARCHAR(50) DEFAULT 'America/Chicago' NOT NULL,
    state VARCHAR(50) DEFAULT 'NEW' NOT NULL,
    last_sankalp_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_users_phone ON users(phone);
CREATE INDEX idx_users_rashi ON users(rashi);
CREATE INDEX idx_users_auspicious_day ON users(auspicious_day);
CREATE INDEX idx_users_state ON users(state);

-- =============================================================================
-- CONVERSATIONS TABLE
-- =============================================================================

CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    state VARCHAR(50) DEFAULT 'NEW' NOT NULL,
    context JSONB DEFAULT '{}' NOT NULL,
    last_inbound_msg_id VARCHAR(255),
    last_outbound_msg_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_conversations_user_id ON conversations(user_id);

-- =============================================================================
-- RASHIPHALALU CACHE TABLE
-- =============================================================================

CREATE TABLE rashiphalalu_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    date DATE NOT NULL,
    rashi VARCHAR(50) NOT NULL,
    language_variant VARCHAR(10) DEFAULT 'te_en' NOT NULL,
    message_text TEXT NOT NULL,
    model VARCHAR(50) DEFAULT 'gpt-4o-mini' NOT NULL,
    prompt_version VARCHAR(20) DEFAULT 'v1' NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    CONSTRAINT uq_rashiphalalu_date_rashi_lang UNIQUE (date, rashi, language_variant)
);

CREATE INDEX idx_rashiphalalu_date ON rashiphalalu_cache(date);
CREATE INDEX idx_rashiphalalu_rashi ON rashiphalalu_cache(rashi);

-- =============================================================================
-- SANKALPS TABLE
-- =============================================================================

CREATE TABLE sankalps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL,
    deity VARCHAR(50),
    auspicious_day VARCHAR(20),
    tier VARCHAR(20) NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD' NOT NULL,
    status VARCHAR(30) DEFAULT 'INITIATED' NOT NULL,
    payment_link_id VARCHAR(255),
    razorpay_ref JSONB,
    receipt_url VARCHAR(500),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_sankalps_user_id ON sankalps(user_id);
CREATE INDEX idx_sankalps_status ON sankalps(status);
CREATE INDEX idx_sankalps_created_at ON sankalps(created_at);

-- =============================================================================
-- PAYMENTS TABLE
-- =============================================================================

CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sankalp_id UUID NOT NULL REFERENCES sankalps(id) ON DELETE CASCADE,
    razorpay_payment_id VARCHAR(255) NOT NULL,
    razorpay_event_id VARCHAR(255) UNIQUE NOT NULL,
    signature_verified BOOLEAN DEFAULT FALSE NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD' NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_payments_sankalp_id ON payments(sankalp_id);
CREATE INDEX idx_payments_razorpay_event_id ON payments(razorpay_event_id);

-- =============================================================================
-- SEVA LEDGER TABLE
-- =============================================================================

CREATE TABLE seva_ledger (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sankalp_id UUID UNIQUE NOT NULL REFERENCES sankalps(id) ON DELETE CASCADE,
    platform_fee DECIMAL(10, 2) NOT NULL,
    seva_amount DECIMAL(10, 2) NOT NULL,
    batch_id VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_seva_ledger_batch_id ON seva_ledger(batch_id);
CREATE INDEX idx_seva_ledger_created_at ON seva_ledger(created_at);

-- =============================================================================
-- SEVA BATCHES TABLE
-- =============================================================================

CREATE TABLE seva_batches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    batch_id VARCHAR(50) UNIQUE NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    total_seva_amount DECIMAL(10, 2) NOT NULL,
    transfer_reference VARCHAR(255),
    transfer_status VARCHAR(20) DEFAULT 'PENDING' NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_seva_batches_batch_id ON seva_batches(batch_id);
CREATE INDEX idx_seva_batches_transfer_status ON seva_batches(transfer_status);

-- =============================================================================
-- TRIGGERS FOR updated_at
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sankalps_updated_at
    BEFORE UPDATE ON sankalps
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
