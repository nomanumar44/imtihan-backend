from django.db import migrations


# slug -> (description, icon)
KNOWN = {
    'ppsc':   ('Punjab Public Service Commission', 'landmark'),
    'fpsc':   ('Federal Public Service Commission', 'flag'),
    'css':    ('Central Superior Services', 'award'),
    'pms':    ('Provincial Management Service', 'crown'),
    'spsc':   ('Sindh Public Service Commission', 'building'),
    'kppsc':  ('Khyber Pakhtunkhwa Public Service Commission', 'shield'),
    'bpsc':   ('Balochistan Public Service Commission', 'building'),
    'ajkpsc': ('AJK Public Service Commission', 'building'),
    'nts':    ('National Testing Service', 'file'),
    'ots':    ('Open Testing Service', 'book'),
}


def seed_exam_meta(apps, schema_editor):
    Exam = apps.get_model('core', 'Exam')
    for exam in Exam.objects.all():
        slug = (exam.slug or '').lower()
        meta = KNOWN.get(slug)
        if not meta:
            continue
        description, icon = meta
        changed = False
        # Only fill description if it's still empty (don't clobber admin edits).
        if not exam.description:
            exam.description = description
            changed = True
        # Only set icon if it's still the default landmark.
        if exam.icon == 'landmark' and icon != 'landmark':
            exam.icon = icon
            changed = True
        if changed:
            exam.save(update_fields=['description', 'icon'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_sectioncontent'),
    ]

    operations = [
        migrations.RunPython(seed_exam_meta, noop),
    ]
