# Adds the default mobile worker role to existing projects that don't yet have one.
from django.db import migrations

from corehq.apps.domain.models import Domain
from corehq.apps.users.models import Permissions
from corehq.apps.users.models_role import UserRole
from corehq.apps.users.role_utils import UserRolePresets
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _add_default_mobile_worker_role(apps, schema_editor):
    for domain in Domain.get_all():
        items = UserRole.objects.filter(domain=domain, is_commcare_user_default=True)
        if len(items) == 0:
            UserRole.create(
                domain,
                UserRolePresets.MOBILE_WORKER,
                permissions=Permissions(),
                is_commcare_user_default=True,
            )
        elif len(items) == 1:
            continue
        else:
            raise Exception(f"More than one role on domain {domain} set as user default")


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0045_add_view_tableau_permission'),
    ]

    operations = [
        migrations.RunPython(_add_default_mobile_worker_role, migrations.RunPython.noop)
    ]
