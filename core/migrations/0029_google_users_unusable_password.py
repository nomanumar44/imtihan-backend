from django.contrib.auth.hashers import check_password, make_password
from django.db import migrations


def disable_empty_passwords(apps, schema_editor):
    """Google-created accounts were saved with a usable hash of '' — make it unusable.

    Only Google-linked profiles are checked; accounts that set a real password
    are left untouched because '' doesn't match their hash.
    """
    User = apps.get_model('auth', 'User')
    google_user_ids = apps.get_model('core', 'Student').objects.exclude(google_id='').values_list('user_id', flat=True)
    for user in User.objects.filter(id__in=list(google_user_ids)).only('id', 'password'):
        if user.password and not user.password.startswith('!') and check_password('', user.password):
            user.password = make_password(None)
            user.save(update_fields=['password'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0028_subject_icons'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(disable_empty_passwords, migrations.RunPython.noop),
    ]
