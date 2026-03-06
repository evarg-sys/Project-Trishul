from django.core.management.base import BaseCommand, CommandError

from api.ml.priority_model import calculate_priority
from api.ml.text_priority_parser import parse_incident_text


class Command(BaseCommand):
    help = "Parse one or more free-text reports and rank priority"

    def add_arguments(self, parser):
        parser.add_argument(
            "--text",
            action="append",
            dest="texts",
            help="Incident report text (repeat --text for multiple incidents)",
        )

    def handle(self, *args, **options):
        texts = options.get("texts") or []
        if not texts:
            raise CommandError("Provide at least one --text value")

        rows = []
        for idx, text in enumerate(texts):
            parsed = parse_incident_text(text)
            score = calculate_priority(
                parsed["severity_score"],
                parsed["population_affected"],
                parsed["response_time_minutes"],
            )
            parsed["priority_score"] = round(score, 4)
            parsed["index"] = idx
            rows.append(parsed)

        rows.sort(key=lambda x: x["priority_score"], reverse=True)
        for rank, row in enumerate(rows, start=1):
            row["rank"] = rank

        self.stdout.write(self.style.SUCCESS("\nPriority Ranking"))
        self.stdout.write("=" * 80)
        for row in rows:
            self.stdout.write(
                f"#{row['rank']} | priority={row['priority_score']:.2f} | "
                f"type={row['disaster_type']} | response={row['response_type']} | "
                f"location={row['location'] or 'N/A'}"
            )
            self.stdout.write(
                f"    severity={row['severity_score']} population={row['population_affected']} "
                f"eta_min={row['response_time_minutes']}"
            )
            self.stdout.write(f"    text={row['raw_text']}")
