\-- Drop tables if they exist to allow clean provisioning runs
DROP TABLE IF EXISTS documents_rag;
DROP TABLE IF EXISTS customers;

\-- 1. Table for Vector RAG (Retrieval-Augmented Generation)
\-- This table stores text chunks and their embeddings from the PDF documents.
\-- NOTE: The vector dimension (1536) should match the embedding model you choose.
\-- We use 1536 as a common default for many large-scale embedding models.
CREATE TABLE documents_rag (
id SERIAL PRIMARY KEY,
document_id VARCHAR(50) NOT NULL,
chunk_index INT NOT NULL,
content TEXT NOT NULL,
metadata JSONB,
embedding VECTOR(1536) -- Placeholder dimension. Adjust based on your LLM embedding model.
);

\-- 2. Table for Structured Queries (Text-to-SQL Demo)
\-- This table is designed to answer natural language questions about customer data.
CREATE TABLE customers (
customer_id SERIAL PRIMARY KEY,
first_name VARCHAR(50),
last_name VARCHAR(50),
email VARCHAR(100),
city VARCHAR(50),
total_orders INT,
signup_date DATE
);

\-- Populate the 'customers' table with sample data
INSERT INTO customers (first_name, last_name, email, city, total_orders, signup_date) VALUES
('Alex', 'Johnson', 'alex.j@example.com', 'New York', 5, '2024-01-15'),
('Ben', 'Carter', 'ben.c@example.com', 'Boston', 2, '2024-03-20'),
('Chloe', 'Davis', 'chloe.d@example.com', 'New York', 12, '2023-11-01'),
('David', 'Miller', 'david.m@example.com', 'Chicago', 8, '2024-05-10'),
('Emily', 'Garcia', 'emily.g@example.com', 'Boston', 1, '2024-07-25');
```eof
