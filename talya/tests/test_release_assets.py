"""Read-only release checks against the staged Git file list and application assets."""

import ast
import csv
import json
import re
import subprocess
import unittest
from pathlib import Path
from xml.etree import ElementTree

from PIL import Image

APP = Path(__file__).resolve().parents[2]
IMAGE_NAMES = (
	"dr-farouq.png",
	"dr-mehira-original.webp",
	"talya-logo.svg",
	"talya-logo-white.svg",
	"talya-mark.svg",
	"talya-reception-styled.png",
	"talya-reception.webp",
)


class TestReleaseAssets(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.files = set(
			subprocess.check_output(
				["git", "-c", f"safe.directory={APP}", "ls-files", "--cached"],
				cwd=APP,
				text=True,
			).splitlines()
		)

	def test_required_images_are_in_git_and_decode(self):
		for name in IMAGE_NAMES:
			with self.subTest(name=name):
				relative = "talya/public/images/" + name
				self.assertIn(relative, self.files)
				if name.endswith(".svg"):
					self.assertTrue(ElementTree.parse(APP / relative).getroot().tag.endswith("svg"))
				else:
					with Image.open(APP / relative) as image:
						image.verify()

	def test_local_asset_references_resolve_to_git_files(self):
		for name in self.files:
			if not name.startswith("talya/") or "/tests/" in name:
				continue
			if Path(name).suffix not in {".html", ".css", ".js", ".py"}:
				continue
			text = (APP / name).read_text()
			if name.endswith(".py"):
				# Hook scaffolding includes commented example assets; inspect actual
				# Python strings rather than treating comments as deployed references.
				text = "\n".join(
					node.value
					for node in ast.walk(ast.parse(text))
					if isinstance(node, ast.Constant) and isinstance(node.value, str)
				)
			for reference in re.findall(r"/assets/talya/([\w./-]+)", text):
				if not reference.endswith("/"):
					self.assertIn("talya/public/" + reference, self.files, (name, reference))
			self.assertNotRegex(text, r"""(?:src|href)=["']/files/""", name)

	def test_communication_modules_and_assets_are_in_git(self):
		for name in (
			"communication.py",
			"inquiries.py",
			"inquiry_import.py",
			"inquiry_labels.py",
			"permissions.py",
			"recipients.py",
			"www/patient_inquiries.py",
			"www/patient_inquiries.html",
			"public/css/patient-inquiries.css",
			"public/js/patient-inquiries.js",
			"tests/browser_support.cjs",
			"tests/test_recipient_safety.py",
			"tests/recipient_safety.browser.cjs",
			"translations/ar.csv",
		):
			self.assertIn("talya/" + name, self.files)
		for doctype in ("talya_patient_inquiry", "talya_communication_settings", "talya_message_dispatch"):
			base = f"talya/talya/doctype/{doctype}/"
			for filename in ("__init__.py", doctype + ".py", doctype + ".json"):
				self.assertIn(base + filename, self.files)

	def test_doctype_safety_defaults_and_field_order(self):
		base = APP / "talya/talya/doctype"
		for name in ("talya_patient_inquiry", "talya_communication_settings", "talya_message_dispatch"):
			data = json.loads((base / name / (name + ".json")).read_text())
			fields = {field["fieldname"]: field for field in data["fields"]}
			self.assertEqual(set(data["field_order"]), set(fields))
			self.assertEqual(len(data["field_order"]), len(fields))
			if name == "talya_communication_settings":
				self.assertEqual(fields["reminders_enabled"]["default"], "0")
				self.assertEqual(fields["require_consent"]["default"], "1")
				self.assertEqual(fields["country_calling_code"]["default"], "971")
			if name == "talya_patient_inquiry":
				for field in ("consent_phone", "recipient_changed_at", "patient_verified_at"):
					self.assertEqual(fields[field]["read_only"], 1)

	def test_translations_are_complete_and_unique(self):
		from talya.inquiry_labels import LABELS

		with (APP / "talya/translations/ar.csv").open() as source:
			rows = list(csv.reader(source))
		catalogue = dict(rows)
		self.assertEqual(len(rows), len(catalogue))
		for label in LABELS:
			self.assertTrue(catalogue.get(label), label)
		for path in (APP / "talya").rglob("*.py"):
			if "tests" in path.parts:
				continue
			for node in ast.walk(ast.parse(path.read_text())):
				if (
					isinstance(node, ast.Call)
					and isinstance(node.func, ast.Name)
					and node.func.id == "_"
					and node.args
					and isinstance(node.args[0], ast.Constant)
				):
					self.assertTrue(catalogue.get(node.args[0].value), (path, node.args[0].value))

	def test_no_site_settings_uploads_or_generated_artifacts_are_in_git(self):
		for name in self.files:
			self.assertNotIn(Path(name).name, {"site_config.json", "common_site_config.json", ".env"})
			self.assertFalse(
				{
					"sites",
					"backups",
					"node_modules",
					"__pycache__",
					".ruff_cache",
					"playwright-report",
				}.intersection(Path(name).parts),
				name,
			)
			self.assertNotRegex(name, r"\.(?:sql(?:\.gz)?|bak|pem|key)$")


if __name__ == "__main__":
	unittest.main()
