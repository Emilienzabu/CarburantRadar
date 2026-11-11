import unittest
from pathlib import Path

BASE=Path(__file__).parent
WORKFLOW=BASE/'.github/workflows/carburant-v19-diagnostic.yml'
if not WORKFLOW.exists():
    WORKFLOW=BASE.parent.parent/'.github/workflows/carburant-v19-diagnostic.yml'
YAML=WORKFLOW.read_text()

class WorkflowTests(unittest.TestCase):
    def test_branch_only_trigger(self):
        self.assertIn('workflow_dispatch:', YAML)
        self.assertIn('\n  push:', YAML)
        self.assertIn('claude/v19-diagnostic-2026-11-11', YAML)
        self.assertIn("'.github/workflows/carburant-v19-diagnostic.yml'", YAML)
        self.assertNotIn('\n  schedule:', YAML)
        self.assertNotIn('\n  pull_request:', YAML)
    def test_readonly_token(self): self.assertIn('contents: read',YAML)
    def test_artifacts_on_failure(self):
        self.assertIn('if: always()',YAML)
        self.assertIn('actions/upload-artifact@v4',YAML)
    def test_no_publication(self):
        self.assertNotIn('youtube',YAML.lower())
        self.assertNotIn('instagram',YAML.lower())
        self.assertNotIn('wrangler',YAML.lower())
    def test_inputs(self):
        for s in ["CITY: ${{ github.event_name == 'push' && 'Lyon' || inputs.city }}","FUEL: ${{ github.event_name == 'push' && 'Gazole' || inputs.fuel }}","INSEE: ${{ github.event_name == 'push' && '' || inputs.insee }}"]:
            self.assertIn(s,YAML)
    def test_safe_shell(self):
        self.assertIn("os.environ['CITY']",YAML)
        self.assertIn('subprocess.call(cmd)',YAML)
    def test_working_directory(self): self.assertIn('working-directory: video/v19',YAML)
    def test_fail_closed(self): self.assertIn("steps.preflight.outputs.exit_code == '0'",YAML)

if __name__=='__main__': unittest.main()
