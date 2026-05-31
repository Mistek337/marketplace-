import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Moderator',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='Ticket',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('product_id', models.UUIDField(db_index=True)),
                ('seller_id', models.UUIDField(db_index=True)),
                ('kind', models.CharField(choices=[('CREATE', 'Create'), ('EDIT', 'Edit')], max_length=16)),
                ('status', models.CharField(
                    choices=[
                        ('PENDING', 'Pending'),
                        ('IN_REVIEW', 'In review'),
                        ('APPROVED', 'Approved'),
                        ('BLOCKED', 'Blocked'),
                        ('HARD_BLOCKED', 'Hard blocked'),
                    ],
                    default='PENDING',
                    max_length=32,
                )),
                ('queue_priority', models.PositiveSmallIntegerField(default=3)),
                ('json_before', models.JSONField(blank=True, null=True)),
                ('json_after', models.JSONField(default=dict)),
                ('product_revision', models.PositiveIntegerField(default=0)),
                ('claimed_revision', models.PositiveIntegerField(blank=True, null=True)),
                ('decision_comment', models.TextField(blank=True, default='')),
                ('claimed_at', models.DateTimeField(blank=True, null=True)),
                ('decision_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assigned_moderator', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='tickets',
                    to='tickets.moderator',
                )),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.CreateModel(
            name='B2BOutboxEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('idempotency_key', models.UUIDField(db_index=True, unique=True)),
                ('event', models.CharField(default='MODERATED', max_length=32)),
                ('product_id', models.UUIDField(db_index=True)),
                ('seller_id', models.UUIDField()),
                ('payload', models.JSONField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('ticket', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='b2b_outbox_events',
                    to='tickets.ticket',
                )),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
    ]
