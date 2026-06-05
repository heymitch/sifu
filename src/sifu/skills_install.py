"""Install the Sifu skill collection (teach-the-agent, make-human-sop) into the
user's agent skills directory so they're available as slash commands / skills.
"""

import shutil
from pathlib import Path

# skills/ lives at the repo root: src/sifu/skills_install.py -> ../../../skills
SKILLS_SRC = Path(__file__).resolve().parent.parent.parent / "skills"


def install_skills(dest, src=None):
    """Copy each skill dir from `src` into `dest`. Returns the names installed."""
    src = Path(src) if src else SKILLS_SRC
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    installed = []
    for skill_dir in sorted(p for p in src.iterdir() if p.is_dir()):
        shutil.copytree(skill_dir, dest / skill_dir.name, dirs_exist_ok=True)
        installed.append(skill_dir.name)
    return installed
