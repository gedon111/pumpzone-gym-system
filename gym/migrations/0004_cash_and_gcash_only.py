"""
The gym takes cash and GCash only. Any old "other" payment becomes cash,
with "was: other" written in its reference so nothing is lost.
"""

from django.db import migrations, models


def other_to_cash(apps, schema_editor):
    Payment = apps.get_model("gym", "Payment")
    for p in Payment.objects.filter(method="other"):
        p.method = "cash"
        p.reference_no = f"was: other {p.reference_no}".strip()[:40]
        p.save(update_fields=["method", "reference_no"])


class Migration(migrations.Migration):
    dependencies = [
        ("gym", "0003_payment_walk_in_plan"),
    ]

    operations = [
        migrations.RunPython(other_to_cash, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="payment",
            name="method",
            field=models.CharField(choices=[("cash", "Cash"), ("gcash", "GCash")], default="cash", max_length=6),
        ),
    ]
