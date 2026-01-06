-- Supabase Setup SQL
-- Run this in Supabase SQL Editor to create the gallery_images table
-- https://supabase.com/dashboard → SQL Editor → New Query

-- Create gallery_images table
CREATE TABLE IF NOT EXISTS gallery_images (
    id SERIAL PRIMARY KEY,
    cloudinary_url VARCHAR NOT NULL,
    caption VARCHAR NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create index on id column (for faster lookups)
CREATE INDEX IF NOT EXISTS ix_gallery_images_id ON gallery_images (id);

-- Create index on created_at for ordering (newest first)
CREATE INDEX IF NOT EXISTS ix_gallery_images_created_at ON gallery_images (created_at DESC);

-- Create trigger to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_gallery_images_updated_at
    BEFORE UPDATE ON gallery_images
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Verify table was created
SELECT
    table_name,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM
    information_schema.columns
WHERE
    table_name = 'gallery_images'
ORDER BY
    ordinal_position;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Gallery images table created successfully!';
    RAISE NOTICE 'You can now use the FastAPI backend to manage gallery images.';
END $$;
