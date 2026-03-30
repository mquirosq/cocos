from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from conversion.models import ConversionTask, Gene

User = get_user_model()

class GeneModelTests(TestCase):
    def test_identifiers_list_normalizes_inputs(self):
        cases = [
            ("", []),
            ("gatA", ["gatA"]),
            (" gatA , gyrA ,, rpoB ", ["gatA", "gyrA", "rpoB"]),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                gene = Gene.objects.create(identifiers=raw)
                self.assertEqual(gene.identifiers_list(), expected)

    def test_add_identifier_avoids_duplicates(self):
        cases = [
            ("", "gatA", ["gatA"]),
            ("gatA", "gyrA", ["gatA", "gyrA"]),
            ("gatA, gyrA", "gatA", ["gatA", "gyrA"]),
        ]
        for initial, to_add, expected in cases:
            with self.subTest(initial=initial, to_add=to_add):
                gene = Gene.objects.create(identifiers=initial)
                gene.add_identifier(to_add)
                gene.refresh_from_db()
                self.assertEqual(gene.identifiers_list(), expected)

    def test_add_identifiers_add_all_identifiers(self):
        gene = Gene.objects.create(identifiers="gatA")
        gene.add_identifiers(["gyrA", "rpoB"])
        gene.refresh_from_db()
        self.assertEqual(set(gene.identifiers_list()), {"gatA", "gyrA", "rpoB"})

    def test_search_identifiers_core_behaviors(self):
        gene_a = Gene.objects.create(identifiers="gatA, gyrA")
        gene_b = Gene.objects.create(identifiers="gatAB")
        gene_c = Gene.objects.create(identifiers="rpoB")

        cases = [
            (["GATA"], {gene_a.id}),
            (["gatA"], {gene_a.id}),
            (["rpoB"], {gene_c.id}),
            (["gatA", "rpoB"], {gene_a.id, gene_c.id}),
            ([], {gene_a.id, gene_b.id, gene_c.id}),
        ]
        for query, expected_ids in cases:
            with self.subTest(query=query):
                result_ids = set(Gene.objects.search_identifiers(query).values_list("id", flat=True))
                self.assertEqual(result_ids, expected_ids)


class TaskModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", password="pass1234")

    def test_conversion_task_external_id_validation(self):
        cases = [
            ("pending", None, False),
            ("pending", "job-0", False),
            ("running", None, True),
            ("running", "job-1", False),
            ("completed", "job-2", False),
        ]
        for status, job_id, should_raise in cases:
            with self.subTest(status=status, job_id=job_id):
                task = ConversionTask(
                    external_job_id=job_id,
                    status=status,
                    input_path="/tmp/input",
                    task_type="annotation",
                    user=self.user,
                )
                if should_raise:
                    with self.assertRaises(ValidationError):
                        task.save()
                else:
                    task.save()
                    self.assertEqual(task.status, status)
