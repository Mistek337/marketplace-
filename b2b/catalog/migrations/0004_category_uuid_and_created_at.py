import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0003_product_sku_uuid_pk"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                    DO $$
                    DECLARE r record;
                    BEGIN
                        FOR r IN
                            SELECT conname, conrelid::regclass AS tbl
                            FROM pg_constraint
                            WHERE contype = 'f'
                              AND confrelid = 'catalog_category'::regclass
                        LOOP
                            EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', r.tbl, r.conname);
                        END LOOP;
                    END $$;

                    ALTER TABLE catalog_category ALTER COLUMN id DROP IDENTITY IF EXISTS;
                    ALTER TABLE catalog_category ALTER COLUMN id DROP DEFAULT;
                    ALTER TABLE catalog_category
                        ALTER COLUMN id TYPE uuid
                        USING ('00000000-0000-0000-0000-' || lpad(to_hex(id), 12, '0'))::uuid;

                    ALTER TABLE catalog_category
                        ALTER COLUMN parent_id TYPE uuid
                        USING CASE
                            WHEN parent_id IS NULL THEN NULL
                            ELSE ('00000000-0000-0000-0000-' || lpad(to_hex(parent_id), 12, '0'))::uuid
                        END;

                    ALTER TABLE catalog_product
                        ALTER COLUMN category_id TYPE uuid
                        USING ('00000000-0000-0000-0000-' || lpad(to_hex(category_id), 12, '0'))::uuid;

                    ALTER TABLE catalog_category
                        ADD COLUMN IF NOT EXISTS created_at timestamp with time zone DEFAULT now();

                    UPDATE catalog_category
                    SET created_at = now()
                    WHERE created_at IS NULL;

                    ALTER TABLE catalog_category
                        ALTER COLUMN created_at SET NOT NULL;

                    ALTER TABLE catalog_category
                        ADD CONSTRAINT catalog_category_parent_id_fk
                        FOREIGN KEY (parent_id) REFERENCES catalog_category(id) DEFERRABLE INITIALLY DEFERRED;

                    ALTER TABLE catalog_product
                        ADD CONSTRAINT catalog_product_category_id_fk
                        FOREIGN KEY (category_id) REFERENCES catalog_category(id) DEFERRABLE INITIALLY DEFERRED;
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                )
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="category",
                    name="id",
                    field=models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                migrations.AddField(
                    model_name="category",
                    name="created_at",
                    field=models.DateTimeField(auto_now_add=True),
                ),
                migrations.AlterField(
                    model_name="category",
                    name="parent",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="children",
                        to="catalog.category",
                    ),
                ),
                migrations.AlterField(
                    model_name="product",
                    name="category",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="products",
                        to="catalog.category",
                    ),
                ),
            ],
        )
    ]
