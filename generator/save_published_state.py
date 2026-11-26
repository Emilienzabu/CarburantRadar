"""Save the state of a published site on top of the latest main without forcing a push."""

import shutil
import subprocess
import sys
import time
from pathlib import Path

STATE = (
    'france/prix-carburant/history.json',
    'generator/generated_pages.json',
    'SEO_REPORT.md',
)


def git(*args, check=True):
    return subprocess.run(['git', *args], check=check).returncode


def changed(*args):
    code = git('diff', '--quiet', *args, check=False)
    if code not in (0, 1):
        raise subprocess.CalledProcessError(code, ['git', 'diff', '--quiet', *args])
    return code == 1


def save(snapshot):
    base = (snapshot / 'generator/etat-generateur-base').read_text(encoding='ascii').strip()
    git('cat-file', '-e', f'{base}^{{commit}}')
    git('config', 'user.name', 'github-actions[bot]')
    git('config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')

    for attempt in range(3):
        git('fetch', '--no-tags', 'origin', 'refs/heads/main')
        git('checkout', '--detach', 'FETCH_HEAD')
        if changed(base, 'HEAD', '--', *STATE):
            print('L’état a déjà changé depuis ce build. Sauvegarde ignorée.')
            return 0

        for path in STATE:
            shutil.copyfile(snapshot / path, path)
        git('add', '--', *STATE)
        if not changed('--cached'):
            return 0
        git('commit', '-m', 'État du générateur (historique des prix, manifeste)')
        if git('push', 'origin', 'HEAD:refs/heads/main', check=False) == 0:
            return 0
        if attempt < 2:
            time.sleep(3 * (attempt + 1))

    print('::error::Le site est en ligne, mais GitHub a refusé la sauvegarde de son état.')
    return 1


if __name__ == '__main__':
    sys.exit(save(Path(sys.argv[1])))
