"""Installing the Sifu skill collection into the user's agent skills dir."""

from sifu.skills_install import install_skills, SKILLS_SRC


def test_install_copies_skill_dirs(tmp_path):
    src = tmp_path / "skills"
    (src / "alpha").mkdir(parents=True)
    (src / "alpha" / "SKILL.md").write_text("x", encoding="utf-8")
    dest = tmp_path / "dest"

    installed = install_skills(dest, src=src)

    assert "alpha" in installed
    assert (dest / "alpha" / "SKILL.md").exists()


def test_shipped_skill_pack_has_the_two_modes():
    names = {p.name for p in SKILLS_SRC.iterdir() if p.is_dir()}
    assert {"teach-the-agent", "make-human-sop"} <= names
