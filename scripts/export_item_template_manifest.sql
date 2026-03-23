-- Run in psql / pgAdmin if you don't use the Python exporter.
-- Save result as CSV and use column id as PNG filename: {id}.png

SELECT id::text AS template_id,
       id::text || '.png' AS filename,
       name
FROM item_templates
ORDER BY name;
