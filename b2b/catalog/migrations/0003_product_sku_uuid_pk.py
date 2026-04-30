import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0002_alter_category_options_category_parent_and_more"),
        ("invoices", "0001_initial"),
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
                              AND confrelid IN ('catalog_product'::regclass, 'catalog_sku'::regclass)
                        LOOP
                            EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', r.tbl, r.conname);
                        END LOOP;
                    END $$;

                    ALTER TABLE catalog_product ALTER COLUMN id DROP IDENTITY IF EXISTS;
                    ALTER TABLE catalog_product ALTER COLUMN id DROP DEFAULT;
                    ALTER TABLE catalog_product
                        ALTER COLUMN id TYPE uuid
                        USING ('00000000-0000-0000-0000-' || lpad(to_hex(id), 12, '0'))::uuid;

                    ALTER TABLE catalog_sku ALTER COLUMN id DROP IDENTITY IF EXISTS;
                    ALTER TABLE catalog_sku ALTER COLUMN id DROP DEFAULT;
                    ALTER TABLE catalog_sku
                        ALTER COLUMN id TYPE uuid
                        USING ('00000000-0000-0000-0000-' || lpad(to_hex(id), 12, '0'))::uuid;

                    ALTER TABLE catalog_productcharacteristic
                        ALTER COLUMN product_id TYPE uuid
                        USING ('00000000-0000-0000-0000-' || lpad(to_hex(product_id), 12, '0'))::uuid;

                    ALTER TABLE catalog_productimage
                        ALTER COLUMN product_id TYPE uuid
                        USING ('00000000-0000-0000-0000-' || lpad(to_hex(product_id), 12, '0'))::uuid;

                    ALTER TABLE catalog_sku
                        ALTER COLUMN product_id TYPE uuid
                        USING ('00000000-0000-0000-0000-' || lpad(to_hex(product_id), 12, '0'))::uuid;

                    ALTER TABLE catalog_skucharacteristic
                        ALTER COLUMN sku_id TYPE uuid
                        USING ('00000000-0000-0000-0000-' || lpad(to_hex(sku_id), 12, '0'))::uuid;

                    ALTER TABLE invoices_invoiceline
                        ALTER COLUMN sku_id TYPE uuid
                        USING ('00000000-0000-0000-0000-' || lpad(to_hex(sku_id), 12, '0'))::uuid;

                    ALTER TABLE catalog_productcharacteristic
                        ADD CONSTRAINT catalog_productcharacteristic_product_id_fk
                        FOREIGN KEY (product_id) REFERENCES catalog_product(id) DEFERRABLE INITIALLY DEFERRED;

                    ALTER TABLE catalog_productimage
                        ADD CONSTRAINT catalog_productimage_product_id_fk
                        FOREIGN KEY (product_id) REFERENCES catalog_product(id) DEFERRABLE INITIALLY DEFERRED;

                    ALTER TABLE catalog_sku
                        ADD CONSTRAINT catalog_sku_product_id_fk
                        FOREIGN KEY (product_id) REFERENCES catalog_product(id) DEFERRABLE INITIALLY DEFERRED;

                    ALTER TABLE catalog_skucharacteristic
                        ADD CONSTRAINT catalog_skucharacteristic_sku_id_fk
                        FOREIGN KEY (sku_id) REFERENCES catalog_sku(id) DEFERRABLE INITIALLY DEFERRED;

                    ALTER TABLE invoices_invoiceline
                        ADD CONSTRAINT invoices_invoiceline_sku_id_fk
                        FOREIGN KEY (sku_id) REFERENCES catalog_sku(id) DEFERRABLE INITIALLY DEFERRED;
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                )
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="product",
                    name="id",
                    field=models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                migrations.AlterField(
                    model_name="sku",
                    name="id",
                    field=models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
            ],
        )
    ]
