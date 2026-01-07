-- Supabase Setup SQL
-- Run this in Supabase SQL Editor to create the gallery_images table
-- https://supabase.com/dashboard → SQL Editor → New Query

-- Drop existing table if you want to recreate from scratch (CAUTION: This deletes all data!)
-- Uncomment the line below only if you want to completely recreate the table
-- DROP TABLE IF EXISTS gallery_images CASCADE;

-- Create gallery_images table with all fields including display_order
CREATE TABLE IF NOT EXISTS gallery_images (
    id SERIAL PRIMARY KEY,
    cloudinary_url VARCHAR NOT NULL,
    caption VARCHAR NULL,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create index on id column (for faster lookups)
CREATE INDEX IF NOT EXISTS ix_gallery_images_id ON gallery_images (id);

-- Create index on created_at for ordering (newest first)
CREATE INDEX IF NOT EXISTS ix_gallery_images_created_at ON gallery_images (created_at DESC);

-- Create index on display_order for custom ordering (used for drag-and-drop reordering in CMS)
CREATE INDEX IF NOT EXISTS ix_gallery_images_display_order ON gallery_images (display_order);

-- Create trigger to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop trigger if it exists, then recreate it
DROP TRIGGER IF EXISTS update_gallery_images_updated_at ON gallery_images;

CREATE TRIGGER update_gallery_images_updated_at
    BEFORE UPDATE ON gallery_images
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- If table already exists and you're adding display_order, run this migration:
-- (Only run if the column doesn't exist - check the verification query below first)
DO $$
BEGIN
    -- Check if display_order column exists
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'gallery_images'
        AND column_name = 'display_order'
    ) THEN
        -- Add display_order column
        ALTER TABLE gallery_images
        ADD COLUMN display_order INTEGER NOT NULL DEFAULT 0;

        -- Create index
        CREATE INDEX ix_gallery_images_display_order
        ON gallery_images(display_order);

        -- Initialize existing images with order based on created_at (newest first)
        UPDATE gallery_images
        SET display_order = subquery.row_num
        FROM (
            SELECT id, ROW_NUMBER() OVER (ORDER BY created_at DESC) as row_num
            FROM gallery_images
        ) as subquery
        WHERE gallery_images.id = subquery.id;

        RAISE NOTICE 'Successfully added display_order column and initialized existing images';
    ELSE
        RAISE NOTICE 'display_order column already exists - skipping migration';
    END IF;
END $$;

-- Verify table structure
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
    RAISE NOTICE '=================================================';
    RAISE NOTICE 'Gallery images table setup completed successfully!';
    RAISE NOTICE '=================================================';
    RAISE NOTICE 'Table includes:';
    RAISE NOTICE '  - id (primary key)';
    RAISE NOTICE '  - cloudinary_url (image URL)';
    RAISE NOTICE '  - caption (optional text)';
    RAISE NOTICE '  - display_order (for drag-and-drop reordering)';
    RAISE NOTICE '  - created_at (timestamp)';
    RAISE NOTICE '  - updated_at (auto-updating timestamp)';
    RAISE NOTICE '=================================================';
    RAISE NOTICE 'You can now use the FastAPI backend to manage gallery images.';
END $$;
