CREATE TABLE IF NOT EXISTS people (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL
);

INSERT INTO people (name) VALUES
    ('Alice'),
    ('Bob');
