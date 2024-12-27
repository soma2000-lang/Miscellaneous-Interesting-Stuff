-- User Transactions Table (Stores all transactions)
CREATE TABLE user_transactions (
    user_id uuid,                    -- Partition key
    transaction_timestamp timestamp, -- Clustering key
    transaction_id uuid,
    transaction_type text,          -- 'SENT' or 'RECEIVED'
    counterparty_id uuid,           -- Other party's user_id
    amount decimal,
    status text,
    metadata map<text, text>,
    PRIMARY KEY (user_id, transaction_timestamp)
) WITH CLUSTERING ORDER BY (transaction_timestamp DESC);

-- P2P Transaction Index Table (For efficient P2P lookups)
CREATE TABLE p2p_transactions (
    user_pair_id text,              -- Composite of both user IDs (smaller_id_larger_id)
    transaction_timestamp timestamp,
    transaction_id uuid,
    amount decimal,
    sender_id uuid,
    receiver_id uuid,
    status text,
    metadata map<text, text>,
    PRIMARY KEY (user_pair_id, transaction_timestamp)
) WITH CLUSTERING ORDER BY (transaction_timestamp DESC);

-- Materialized View for Recent Transactions
CREATE MATERIALIZED VIEW recent_transactions_mv AS
    SELECT *
    FROM user_transactions
    WHERE user_id IS NOT NULL
    AND transaction_timestamp IS NOT NULL
    PRIMARY KEY (user_id, transaction_timestamp);
