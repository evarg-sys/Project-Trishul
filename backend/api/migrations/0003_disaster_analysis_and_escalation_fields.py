from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0002_disaster_resolution_notes_disaster_resolved_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='disaster',
            name='analysis_details',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='disaster',
            name='capability_match',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='disaster',
            name='final_plan',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='disaster',
            name='alerts',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='disaster',
            name='needs_operator_review',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='disaster',
            name='needs_mutual_aid',
            field=models.BooleanField(default=False),
        ),
    ]
