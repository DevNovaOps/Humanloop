# Migration: Add OrgMember model for org-scoped team management page

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrgMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
                ('email', models.EmailField(max_length=254)),
                ('job_role', models.CharField(default='Member', max_length=100)),
                ('organization', models.CharField(default='', max_length=200)),
                ('joined', models.DateField(auto_now_add=True)),
                ('added_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='added_members',
                    to='core.user',
                )),
            ],
            options={
                'db_table': 'org_members',
                'unique_together': {('email', 'organization')},
            },
        ),
    ]
