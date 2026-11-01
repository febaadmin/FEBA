"""
manage.py plugnmeet_health — état de l'instance plugNmeet (sans secret).

Codes de sortie : 0 opérationnelle, 1 dégradée ou non configurée.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Diagnostic de l'instance plugNmeet auto-hébergée."

    def handle(self, *args, **options):
        from apps.virtualclass.plugnmeet import health

        result = health()
        self.stdout.write(f"plugNmeet : {result['status']} - {result['server_url'] or '(non configuré)'}")
        for check in result["checks"]:
            style = self.style.SUCCESS if check["ok"] else self.style.ERROR
            self.stdout.write(style(f"  [{'OK' if check['ok'] else 'KO'}] {check['name']} : {check['detail']}"))
        if result["status"] != "operational":
            self.stderr.write(self.style.ERROR(result["detail"]))
            raise SystemExit(1)
