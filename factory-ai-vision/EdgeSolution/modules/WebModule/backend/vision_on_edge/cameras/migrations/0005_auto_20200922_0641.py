# Generated by Django 3.0.8 on 2020-09-22 06:41

import json
import uuid

from django.db import migrations, models


def gen_default_lines():
    """gen_default_lines."""
    template = {
        "useCountingLine": True,
        "countingLines": [
            {
                "id": "$UUID_PLACE_HOLDER",
                "type": "Line",
                "label": [{"x": 229, "y": 215}, {"x": 916, "y": 255}],
            }
        ],
    }
    template["countingLines"][0]["id"] = str(uuid.uuid4())
    return json.dumps(template)


def gen_default_zones():
    """gen_default_zones."""
    template = {
        "useDangerZone": True,
        "dangerZones": [
            {
                "id": "$UUID_PLACE_HOLDER",
                "type": "BBox",
                "label": {"x1": 23, "y1": 58, "x2": 452, "y2": 502},
            }
        ],
    }
    template["dangerZones"][0]["id"] = str(uuid.uuid4())
    return json.dumps(template)


class Migration(migrations.Migration):

    dependencies = [("cameras", "0004_camera_danger_zones")]

    operations = [
        migrations.AlterField(
            model_name="camera",
            name="danger_zones",
            field=models.CharField(
                blank=True, default=gen_default_zones, max_length=1000
            ),
        ),
        migrations.AlterField(
            model_name="camera",
            name="lines",
            field=models.CharField(
                blank=True, default=gen_default_lines, max_length=1000
            ),
        ),
    ]