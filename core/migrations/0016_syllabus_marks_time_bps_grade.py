# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0015_syllabus_slug_alter_joblisting_status_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='syllabus',
            name='bps_grade',
            field=models.CharField(max_length=50, blank=True, default='', help_text='e.g., BPS-14'),
        ),
        migrations.AddField(
            model_name='syllabus',
            name='marks',
            field=models.PositiveIntegerField(blank=True, null=True, help_text='Total marks for the exam'),
        ),
        migrations.AddField(
            model_name='syllabus',
            name='time',
            field=models.CharField(max_length=50, blank=True, default='', help_text='e.g., 90 minutes'),
        ),
    ]
