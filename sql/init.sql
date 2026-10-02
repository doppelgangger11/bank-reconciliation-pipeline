CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS clean;
CREATE SCHEMA IF NOT EXISTS reports;

CREATE TABLE staging.bank_transactions (
    id SERIAL PRIMARY KEY,
    transaction_id TEXT,
    account_id TEXT,
    amount NUMERIC,
    currency TEXT,
    transaction_date TEXT, -- намеренно TEXT, у нас разные форматы дат
    raw_row JSONB
);

CREATE TABLE staging.ledger_records (
    id SERIAL PRIMARY KEY,
    record_id TEXT,
    account_id TEXT,
    amount NUMERIC,
    currency TEXT,
    record_date TEXT,
    raw_row JSONB
);

CREATE TABLE clean.bank_transactions_clean (
    id SERIAL PRIMARY KEY,
    transaction_id TEXT,
    account_id TEXT,
    amount NUMERIC(14, 2),
    currency TEXT,
    transaction_date DATE
);

CREATE TABLE clean.ledger_records_clean (
    id SERIAL PRIMARY KEY,
    record_id TEXT,
    account_id TEXT,
    amount NUMERIC(14, 2),
    currency TEXT,
    record_date DATE
);